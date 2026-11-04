#!/bin/bash
# Server health (0.22.0, decision 056), with plain Linux tools: no monitoring stack (the
# e2-micro has 1 GB of RAM).
#   health.sh            report in the terminal: now, the last 24 hours, containers, timers
#   health.sh --collect  append one sample to $DIR/saude/amostras.jsonl (systemd timer, every
#                        5 minutes; 7 days kept). The web app reads that file, mounted
#                        read-only, and never gets access to Docker itself. Also checks the
#                        site through the internet and signals the external monitor.
# The folder, the file and the samples' fields keep their names: the app reads them
# (apps/monitoring/health.py), and they change with it.
set -euo pipefail
export LC_ALL=C  # numbers with a dot, whatever the server's language
source "$(dirname "$0")/common.sh"

HEALTH_DIR="$DIR/saude"
SAMPLES="$HEALTH_DIR/amostras.jsonl"
KEEP=2016  # 7 days of 5-minute samples

# CPU busy and steal (time taken by other VMs on the shared core), in %, over 2 seconds.
cpu() {
  local a b
  a=$(head -1 /proc/stat)
  sleep 2
  b=$(head -1 /proc/stat)
  awk -v a="$a" -v b="$b" 'BEGIN {
    split(a, x); split(b, y)
    for (i = 2; i <= 9; i++) { t += y[i] - x[i] }
    idle = (y[5] + y[6]) - (x[5] + x[6]); steal = y[9] - x[9]
    if (t <= 0) t = 1
    printf "%.1f %.1f", 100 * (t - idle - steal) / t, 100 * steal / t
  }'
}

memory() {  # total, available, swap total, swap free (kB)
  awk '/^MemTotal:/ {t=$2} /^MemAvailable:/ {a=$2} /^SwapTotal:/ {st=$2} /^SwapFree:/ {sf=$2}
       END {print t, a, st, sf}' /proc/meminfo
}

network() {  # bytes received and sent since boot by the real interfaces (not docker's)
  awk -F'[: ]+' 'NR > 2 && $2 !~ /^(lo|docker|veth|br-)/ {rx += $3; tx += $11} END {print rx+0, tx+0}' \
    /proc/net/dev
}

containers() {  # JSON array: name, CPU % and memory of each container
  local lines
  lines=$(docker stats --no-stream --format \
    '{"nome":"{{.Name}}","cpu":"{{.CPUPerc}}","memoria":"{{.MemUsage}}","memoria_pct":"{{.MemPerc}}"}' \
    2>/dev/null | paste -sd, -)
  echo "[${lines}]"
}

collect() {
  mkdir -p "$HEALTH_DIR"
  read -r busy steal <<<"$(cpu)"
  read -r mem_total mem_available swap_total swap_free <<<"$(memory)"
  read -r disk_total disk_used <<<"$(df -B1 --output=size,used / | tail -1)"
  read -r rx tx <<<"$(network)"
  read -r l1 l5 l15 _ <"/proc/loadavg"
  read -r uptime _ <"/proc/uptime"
  printf '{"momento":"%s","cpu":%s,"cpu_roubada":%s,"carga":[%s,%s,%s],"memoria_total":%s,"memoria_disponivel":%s,"swap_total":%s,"swap_livre":%s,"disco_total":%s,"disco_usado":%s,"rede_recebido":%s,"rede_enviado":%s,"ligado_ha":%.0f,"containers":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$busy" "$steal" "$l1" "$l5" "$l15" \
    "$((mem_total * 1024))" "$((mem_available * 1024))" "$((swap_total * 1024))" "$((swap_free * 1024))" \
    "$disk_total" "$disk_used" "$rx" "$tx" "$uptime" "$(containers)" >>"$SAMPLES"
  # Keep only the last 7 days (replaced atomically: the app may be reading it).
  if [ "$(wc -l <"$SAMPLES")" -gt "$KEEP" ]; then
    tail -n "$KEEP" "$SAMPLES" >"$SAMPLES.new"
    mv -f "$SAMPLES.new" "$SAMPLES"
  fi
  chmod 644 "$SAMPLES"
}

report() {
  echo "== Server: $(hostname), up $(uptime -p | sed 's/^up //')"
  echo "Load (1, 5, 15 min): $(cut -d' ' -f1-3 /proc/loadavg) on $(nproc) cores"
  read -r busy steal <<<"$(cpu)"
  echo "Processor now: ${busy}% busy, ${steal}% taken by other machines"
  echo
  echo "== Memory"
  free -h
  echo
  echo "== Disk"
  df -h /
  echo
  echo "== Containers"
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
  echo
  echo "== Last 24 hours and last backup"
  manage health -- saude 2>/dev/null \
    || echo "(the system is down: no summary of the last 24 hours)"
  echo
  echo "== Scheduled tasks"
  systemctl list-timers 'kaladrius-*' --no-pager | head -n -3
  if systemctl --failed --no-legend 'kaladrius-*' | grep . >/dev/null; then
    echo
    echo "!! Failed:"
    systemctl --failed --no-legend 'kaladrius-*'
  fi
}

# Signal $1 with success when the rest of the arguments (a command) succeeds, failure if not.
signal_of() {
  local monitor=$1
  shift
  if "$@"; then notify_monitor "$monitor"; else notify_monitor "$monitor" fail; fi
}

# Days until the HTTPS certificate of $1 expires (0 when it cannot be read).
certificate_days() {
  local expiry end
  site_curl_options "$1"  # common.sh
  expiry=$(curl -sv -m 20 "${CURL_OPTIONS[@]}" -o /dev/null "https://$1/" 2>&1 | sed -n 's/^\*[[:space:]]*expire date: //p' | head -1)
  end=$(date -d "$expiry" +%s 2>/dev/null || echo 0)
  echo $(((end - $(date +%s)) / 86400))
}

# The hostnames of a variable of .env ("a.example, b.example"), one per line.
hosts_of() {
  env_value "$1" | tr ',' '\n' | tr -d ' ' | grep -v '^$' || true
}

# Every hostname answers `path` over HTTPS.
all_answer() {
  local path=$1 host
  shift
  for host in "$@"; do
    site_curl_options "$host"  # common.sh
    curl -fsS -m 20 "${CURL_OPTIONS[@]}" -o /dev/null "https://$host$path" || return 1
  done
}

# No certificate of these hostnames expires in less than 14 days: Caddy renews them about 30
# days before, so 14 days left means renewing is failing.
certificates_ok() {
  local host
  for host in "$@"; do
    [ "$(certificate_days "$host")" -ge 14 ] || return 1
  done
}

# What anyone sees, through the internet and by the server's addresses, for the external
# monitor (decisions 078 and 079). Each check is independent and never stops the others.
# Every hostname is checked (SITE_HOSTNAME and DOCS_HOSTNAME may list several, decision 134).
check_sites() {
  local -a sites docs
  mapfile -t sites < <(hosts_of SITE_HOSTNAME)
  mapfile -t docs < <(hosts_of DOCS_HOSTNAME)
  # The system, with its database (/api/v1/saude answers 503 when the database does not).
  signal_of MONITOR_SYSTEM_URL all_answer /api/v1/saude "${sites[@]}"
  # On the internal network Caddy's local certificates last hours and are renewed by it: there
  # is no expiry to watch.
  internal_network || signal_of MONITOR_CERTIFICATE_URL certificates_ok "${sites[@]}" "${docs[@]}"
  if [ "${#docs[@]}" -gt 0 ]; then
    signal_of MONITOR_DOCS_URL all_answer / "${docs[@]}"
  fi
}

# After a sample: failure when memory, swap or disk is critical (the same limits as the web
# app's health page, apps/monitoring/health.py LIMITES; not the processor, whose peaks are
# normal).
resources_ok() {
  local memory_pct swap_pct disk_pct
  memory_pct=$((100 * (mem_total - mem_available) / (mem_total > 0 ? mem_total : 1)))
  swap_pct=$((swap_total > 0 ? 100 * (swap_total - swap_free) / swap_total : 0))
  disk_pct=$((100 * disk_used / (disk_total > 0 ? disk_total : 1)))
  [ "$memory_pct" -lt 95 ] && [ "$swap_pct" -lt 80 ] && [ "$disk_pct" -lt 90 ]
}

case "${1:-}" in
  --collect | --coletar)
    check_sites
    collect
    signal_of MONITOR_RESOURCES_URL resources_ok
    ;;
  *) report ;;
esac

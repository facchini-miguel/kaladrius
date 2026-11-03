#!/bin/bash
# Server health (0.22.0, decision 056), with plain Linux tools: no monitoring stack (the
# e2-micro has 1 GB of RAM).
#   saude.sh            report in the terminal: now, the last 24 hours, containers, timers
#   saude.sh --coletar  append one sample to $DIR/saude/amostras.jsonl (systemd timer, every
#                       5 minutes; 7 days kept). The web app reads that file, mounted
#                       read-only, and never gets access to Docker itself. Also checks the
#                       site through the internet and signals the external monitor.
set -euo pipefail
export LC_ALL=C  # numbers with a dot, whatever the server's language
source "$(dirname "$0")/comum.sh"

PASTA="$DIR/saude"
AMOSTRAS="$PASTA/amostras.jsonl"
GUARDAR=2016  # 7 days of 5-minute samples

# CPU busy and steal (time taken by other VMs on the shared core), in %, over 2 seconds.
cpu() {
  local a b
  a=$(head -1 /proc/stat)
  sleep 2
  b=$(head -1 /proc/stat)
  awk -v a="$a" -v b="$b" 'BEGIN {
    split(a, x); split(b, y)
    for (i = 2; i <= 9; i++) { t += y[i] - x[i] }
    ocioso = (y[5] + y[6]) - (x[5] + x[6]); roubado = y[9] - x[9]
    if (t <= 0) t = 1
    printf "%.1f %.1f", 100 * (t - ocioso - roubado) / t, 100 * roubado / t
  }'
}

memoria() {  # total, available, swap total, swap free (kB)
  awk '/^MemTotal:/ {t=$2} /^MemAvailable:/ {d=$2} /^SwapTotal:/ {st=$2} /^SwapFree:/ {sl=$2}
       END {print t, d, st, sl}' /proc/meminfo
}

rede() {  # bytes received and sent since boot by the real interfaces (not docker's)
  awk -F'[: ]+' 'NR > 2 && $2 !~ /^(lo|docker|veth|br-)/ {rx += $3; tx += $11} END {print rx+0, tx+0}' \
    /proc/net/dev
}

containers() {  # JSON array: name, CPU % and memory of each container
  local linhas
  linhas=$(docker stats --no-stream --format \
    '{"nome":"{{.Name}}","cpu":"{{.CPUPerc}}","memoria":"{{.MemUsage}}","memoria_pct":"{{.MemPerc}}"}' \
    2>/dev/null | paste -sd, -)
  echo "[${linhas}]"
}

coletar() {
  mkdir -p "$PASTA"
  read -r uso roubado <<<"$(cpu)"
  read -r mem_total mem_disp swap_total swap_livre <<<"$(memoria)"
  read -r disco_total disco_usado <<<"$(df -B1 --output=size,used / | tail -1)"
  read -r rx tx <<<"$(rede)"
  read -r c1 c5 c15 _ <"/proc/loadavg"
  read -r ligado _ <"/proc/uptime"
  printf '{"momento":"%s","cpu":%s,"cpu_roubada":%s,"carga":[%s,%s,%s],"memoria_total":%s,"memoria_disponivel":%s,"swap_total":%s,"swap_livre":%s,"disco_total":%s,"disco_usado":%s,"rede_recebido":%s,"rede_enviado":%s,"ligado_ha":%.0f,"containers":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$uso" "$roubado" "$c1" "$c5" "$c15" \
    "$((mem_total * 1024))" "$((mem_disp * 1024))" "$((swap_total * 1024))" "$((swap_livre * 1024))" \
    "$disco_total" "$disco_usado" "$rx" "$tx" "$ligado" "$(containers)" >>"$AMOSTRAS"
  # Keep only the last 7 days (replaced atomically: the app may be reading it).
  if [ "$(wc -l <"$AMOSTRAS")" -gt "$GUARDAR" ]; then
    tail -n "$GUARDAR" "$AMOSTRAS" >"$AMOSTRAS.novo"
    mv -f "$AMOSTRAS.novo" "$AMOSTRAS"
  fi
  chmod 644 "$AMOSTRAS"
}

relatorio() {
  echo "== Servidor: $(hostname), ligado $(uptime -p | sed 's/^up //')"
  echo "Carga (1, 5, 15 min): $(cut -d' ' -f1-3 /proc/loadavg) em $(nproc) núcleos"
  read -r uso roubado <<<"$(cpu)"
  echo "Processador agora: ${uso}% em uso, ${roubado}% tomado por outras máquinas"
  echo
  echo "== Memória"
  free -h
  echo
  echo "== Disco"
  df -h /
  echo
  echo "== Containers"
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
  echo
  echo "== Últimas 24 horas e último backup"
  compose exec -T app python manage.py saude 2>/dev/null \
    || echo "(o sistema está fora do ar: sem o resumo das 24 horas)"
  echo
  echo "== Tarefas agendadas"
  systemctl list-timers 'kaladrius-*' --no-pager | head -n -3
  if systemctl --failed --no-legend 'kaladrius-*' | grep . >/dev/null; then
    echo
    echo "!! Com falha:"
    systemctl --failed --no-legend 'kaladrius-*'
  fi
}

# Signal $1 with success when the rest of the arguments (a command) succeeds, failure if not.
sinal_de() {
  local monitor=$1
  shift
  if "$@"; then avisar_monitor "$monitor"; else avisar_monitor "$monitor" fail; fi
}

# Days until the HTTPS certificate of $1 expires (0 when it cannot be read).
dias_do_certificado() {
  local validade fim
  opcoes_para_o_site "$1"  # comum.sh
  validade=$(curl -sv -m 20 "${OPCOES_CURL[@]}" -o /dev/null "https://$1/" 2>&1 | sed -n 's/^\*[[:space:]]*expire date: //p' | head -1)
  fim=$(date -d "$validade" +%s 2>/dev/null || echo 0)
  echo $(((fim - $(date +%s)) / 86400))
}

# The hostnames of a variable of .env ("a.example, b.example"), one per line.
hosts_de() {
  valor_do_env "$1" | tr ',' '\n' | tr -d ' ' | grep -v '^$' || true
}

# Every hostname answers `caminho` over HTTPS.
todos_respondem() {
  local caminho=$1 host
  shift
  for host in "$@"; do
    opcoes_para_o_site "$host"  # comum.sh
    curl -fsS -m 20 "${OPCOES_CURL[@]}" -o /dev/null "https://$host$caminho" || return 1
  done
}

# No certificate of these hostnames expires in less than 14 days: Caddy renews them about 30
# days before, so 14 days left means renewing is failing.
certificados_ok() {
  local host
  for host in "$@"; do
    [ "$(dias_do_certificado "$host")" -ge 14 ] || return 1
  done
}

# What anyone sees, through the internet and by the server's addresses, for the external
# monitor (decisions 078 and 079). Each check is independent and never stops the others.
# Every hostname is checked (SITE_HOSTNAME and DOCS_HOSTNAME may list several, decision 134).
verificar() {
  local -a sites docs
  mapfile -t sites < <(hosts_de SITE_HOSTNAME)
  mapfile -t docs < <(hosts_de DOCS_HOSTNAME)
  # The system, with its database (/api/v1/saude answers 503 when the database does not).
  sinal_de MONITOR_SISTEMA_URL todos_respondem /api/v1/saude "${sites[@]}"
  # On the internal network Caddy's local certificates last hours and are renewed by it: there
  # is no expiry to watch.
  rede_interna || sinal_de MONITOR_CERTIFICADO_URL certificados_ok "${sites[@]}" "${docs[@]}"
  if [ "${#docs[@]}" -gt 0 ]; then
    sinal_de MONITOR_DOCS_URL todos_respondem / "${docs[@]}"
  fi
}

# After a sample: failure when memory, swap or disk is critical (the same limits as the web
# app's health page, apps/monitoring/health.py LIMITES; not the processor, whose peaks are
# normal).
recursos_ok() {
  local memoria swap disco
  memoria=$((100 * (mem_total - mem_disp) / (mem_total > 0 ? mem_total : 1)))
  swap=$((swap_total > 0 ? 100 * (swap_total - swap_livre) / swap_total : 0))
  disco=$((100 * disco_usado / (disco_total > 0 ? disco_total : 1)))
  [ "$memoria" -lt 95 ] && [ "$swap" -lt 80 ] && [ "$disco" -lt 90 ]
}

if [ "${1:-}" = "--coletar" ]; then
  verificar
  coletar
  sinal_de MONITOR_RECURSOS_URL recursos_ok
else
  relatorio
fi

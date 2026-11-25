#!/bin/bash
# The reference production's update on the VPS, where Dokploy runs the Compose (decision 208),
# with the version and never latest (decision 217). The Compose in Dokploy names
#   app:   image: ghcr.io/facchini-miguel/kaladrius:X.Y.Z
#   docs:  context: https://github.com/facchini-miguel/kaladrius.git#vX.Y.Z:docs
# Every 5 minutes (kaladrius-update.timer) this script reads the repository's newest release on
# GitHub (vX.Y.Z: CI creates it only after the version's image is on ghcr.io and its Linux
# packages are built, decision 119). When that version is newer than the Compose's, it changes
# those two lines through Dokploy's API (nothing else of the Compose), deploys, and waits until
# /api/v1/health answers with the database and that version. It never goes down by itself.
#
# A version that does not come up (decision 135): the previous Compose goes back and is deployed,
# the version is refused (skipped until a newer one comes out, or until it is named by hand) and
# the update monitor reports the failure on every run until then. Migrations already applied are
# not undone.
#
#   update-dokploy.sh            the newest version, when it is newer than the Compose's
#   update-dokploy.sh --check    only says what it would do
#   update-dokploy.sh X.Y.Z      that version now (an older one too: a rollback), and held: the
#                                timer leaves it there until --release
#   update-dokploy.sh --release  follows the newest version again (and forgets the refusal)
#
# A Compose that still names :latest (before decision 217) gets the newest version on the first
# run. Only that version's image is pulled: a merge that does not raise the version changes
# nothing in production.
set -euo pipefail
source "$(dirname "$0")/common.sh"
trap 'notify_monitor MONITOR_UPDATE_URL fail' ERR

REPOSITORY=facchini-miguel/kaladrius
IMAGE=ghcr.io/$REPOSITORY
SITE=${SITE:-kaladrius.facchini.eti.br}
COMPOSE_ID_FILE=${COMPOSE_ID_FILE:-/home/facchini/.kaladrius-compose-id}
KEY_FILE=${KEY_FILE:-/home/facchini/.dokploy-api-key}
DOKPLOY=${DOKPLOY:-http://127.0.0.1:3000}
RELEASES=${RELEASES:-https://api.github.com/repos/$REPOSITORY/releases/latest}
# The held version, the refused one and the previous Compose.
STATE=${STATE:-$DIR/version}
DEPLOY_INTERVAL=${DEPLOY_INTERVAL:-10}
HEALTH_INTERVAL=${HEALTH_INTERVAL:-5}
VERSION_RE='^[0-9]+\.[0-9]+\.[0-9]+$'

case "${1:-}" in
  "") mode=follow ;;
  --check) mode=check ;;
  --release) mode=release ;;
  *)
    if [[ "$1" =~ $VERSION_RE ]]; then
      mode=hold wanted=$1
    else
      echo "Usage: $0 [--check | --release | X.Y.Z]" >&2
      exit 2
    fi
    ;;
esac

# One run at a time: a run by hand waits for the timer's.
exec 9>"$DIR/update.lock"
flock 9
mkdir -p "$STATE"
WORK=$(mktemp -d)
maintenance=0
# shellcheck disable=SC2329  # the EXIT trap calls it
finish() {
  rm -rf "$WORK"
  if [ "$maintenance" = 1 ]; then end_maintenance; fi
}
trap finish EXIT

api() {  # api <route> [file with the JSON body]
  curl -fsS -m 60 -H "x-api-key: $(tr -d '[:space:]' <"$KEY_FILE")" -H "Content-Type: application/json" \
    ${2:+--data-binary "@$2"} "$DOKPLOY/api/$1"
}

# The Compose's text in $WORK/<file> and its status ("running" while Dokploy deploys it). Only
# those two: compose.one also brings the Compose's variables, the app's secrets.
compose_read() {  # compose_read <file>
  api "compose.one?composeId=$id" | OUT="$WORK/$1" python3 -c '
import json, os, sys
d = json.load(sys.stdin)
open(os.environ["OUT"], "w").write(d["composeFile"] or "")
print(d["composeStatus"])'
}

compose_put() {  # compose_put <file>: the Compose's text in Dokploy
  ID="$id" python3 -c '
import json, os, sys
print(json.dumps({"composeId": os.environ["ID"], "composeFile": open(sys.argv[1]).read()}))' \
    "$WORK/$1" > "$WORK/update.json"
  api compose.update "$WORK/update.json" >/dev/null
}

# Reads (and with <out> <version>, rewrites) the app's image line and the docs' build context:
# exactly one of each, or it stops. Prints "<the app's tag> <the docs' git ref>".
compose_lines() {  # compose_lines <in> [<out> <version>]
  python3 - "$WORK/$1" ${2:+"$WORK/$2"} ${3:+"$3"} <<'PY'
import re, sys
text = open(sys.argv[1]).read()
app = re.compile(r"""^(\s*image:\s*["']?ghcr\.io/facchini-miguel/kaladrius:)([^"'\s@#]+)""", re.M)
docs = re.compile(r"""^(\s*context:\s*["']?https://github\.com/facchini-miguel/kaladrius\.git#)([^:"'\s]+)(:docs)""", re.M)
found = [m for m in app.finditer(text)], [m for m in docs.finditer(text)]
if len(found[0]) != 1:
    sys.exit(f"the Compose has {len(found[0])} image lines of ghcr.io/facchini-miguel/kaladrius, not one")
if len(found[1]) != 1:
    sys.exit(f"the Compose has {len(found[1])} build contexts of the docs from the repository, not one")
print(found[0][0][2], found[1][0][2])
if len(sys.argv) > 2:
    version = sys.argv[3]
    text = app.sub(lambda m: m[1] + version, text, count=1)
    text = docs.sub(lambda m: m[1] + "v" + version + m[3], text, count=1)
    open(sys.argv[2], "w").write(text)
PY
}

newer() {  # newer <a> <b>: a is a version above b (b may be "latest" or a branch: never above)
  python3 -c '
import re, sys
a, b = sys.argv[1], sys.argv[2]
v = lambda s: tuple(int(n) for n in s.split(".")) if re.fullmatch(r"\d+\.\d+\.\d+", s) else None
sys.exit(0 if v(a) and (v(b) is None or v(a) > v(b)) else 1)' "$1" "$2"
}

newest_version() {  # the tag of the repository's newest release, without the v
  local tag
  tag=$(curl -fsS -m 30 -A kaladrius-update -H "Accept: application/vnd.github+json" "$RELEASES" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["tag_name"])')
  tag=${tag#v}
  [[ "$tag" =~ $VERSION_RE ]] || { echo "The newest release is not a version: $tag" >&2; return 1; }
  echo "$tag"
}

deployed() {  # deployed <title>: Dokploy deploys the Compose and finishes it as "done"
  local status
  printf '{"composeId": "%s", "title": "%s"}' "$id" "$1" > "$WORK/deploy.json"
  api compose.deploy "$WORK/deploy.json" >/dev/null || return 1
  for _ in $(seq 1 90); do
    sleep "$DEPLOY_INTERVAL"
    status=$(compose_read deployed.yml)
    [ "$status" = running ] || break
  done
  [ "$status" = "done" ] || { echo "Dokploy's deploy ended as: $status" >&2; return 1; }
}

answers() {  # answers <version>: /api/v1/health answers with the database and that version (any, when empty)
  local end body
  site_curl_options "$SITE"
  end=$(($(date +%s) + HEALTH_WAIT))
  while :; do
    body=$(curl -fsS -m 10 "${CURL_OPTIONS[@]}" "https://$SITE/api/v1/health" 2>/dev/null || true)
    if VERSION="$1" python3 -c '
import json, os, sys
d = json.loads(sys.argv[1] or "{}")
sys.exit(0 if d.get("database") is True and os.environ["VERSION"] in ("", d.get("version")) else 1)' "$body" 2>/dev/null; then
      return 0
    fi
    [ "$(date +%s)" -lt "$end" ] || { echo "The system answers: ${body:-nothing}" >&2; return 1; }
    sleep "$HEALTH_INTERVAL"
  done
}

id=$(tr -d '[:space:]' <"$COMPOSE_ID_FILE")
if [ "$mode" = release ]; then
  rm -f "$STATE/held" "$STATE/refused"
  echo "Following the newest version again."
fi
held=$(cat "$STATE/held" 2>/dev/null || true)
refused=$(cat "$STATE/refused" 2>/dev/null || true)
if [ "$mode" = hold ]; then
  target=$wanted
elif [ -n "$held" ] && [ "$mode" != release ]; then
  target=$held
else
  target=$(newest_version)
fi

status=$(compose_read current.yml)
if [ "$status" = running ]; then
  echo "Dokploy deploys the Compose now: the next run looks again."
  notify_monitor MONITOR_UPDATE_URL
  exit 0
fi
lines=$(compose_lines current.yml)  # an assignment, so that a Compose it cannot read stops here
read -r current docs_ref <<<"$lines"

if [ "$current" = "$target" ] && [ "$docs_ref" = "v$target" ]; then
  [ "$mode" = hold ] && echo "$target" > "$STATE/held" && echo "Held at $target."
  [ "$mode" = check ] && echo "On $target${held:+ (held)}: nothing to do."
  [ "$mode" = check ] || notify_monitor MONITOR_UPDATE_URL
  exit 0
fi
if [ "$mode" != hold ] && [ -z "$held" ] && newer "$current" "$target"; then
  echo "The Compose has $current, above the newest release ($target): nothing changed (never down by itself)."
  [ "$mode" = check ] || notify_monitor MONITOR_UPDATE_URL
  exit 0
fi
if [ "$mode" != hold ] && [ "$target" = "$refused" ]; then
  echo "$target did not come up last time and is refused: the system stays on $current."
  [ "$mode" = check ] || notify_monitor MONITOR_UPDATE_URL fail
  exit 0
fi

compose_lines current.yml new.yml "$target" >/dev/null
echo "The Compose: $current -> $target (the app's image and the docs' tag)."
if [ "$mode" = check ]; then
  diff -u "$WORK/current.yml" "$WORK/new.yml" | tail -n +3 | grep '^[-+]' | sed 's/^/  /' || true
  echo "Would pull $IMAGE:$target, put the two lines in the Compose, deploy it and wait for /api/v1/health."
  exit 0
fi

docker pull -q "$IMAGE:$target" >/dev/null  # a failure changes nothing and tells the monitor
cp "$WORK/current.yml" "$STATE/compose-previous.yml"
compose_put new.yml
# The app restarts: health.sh does not report the stop meanwhile (decision 209).
begin_maintenance
maintenance=1
if deployed "Kaladrius $target" && answers "$target"; then
  maintenance=0
  end_maintenance
  rm -f "$STATE/refused"
  if [ "$mode" = hold ]; then echo "$target" > "$STATE/held"; fi
  # For the operations dashboard in Grafana (decision 211).
  write_metrics update <<EOF
# HELP kaladrius_update_last_success_timestamp_seconds When the system was last updated.
# TYPE kaladrius_update_last_success_timestamp_seconds gauge
kaladrius_update_last_success_timestamp_seconds $(date +%s)
EOF
  if [ "$mode" = hold ]; then echo "Updated to $target, held (--release follows the newest again)."; else echo "Updated to $target."; fi
  notify_monitor MONITOR_UPDATE_URL
  exit 0
fi

# Did not come up: the previous Compose goes back, and this version is refused.
echo "$target" > "$STATE/refused"
echo "$target did not come up: the previous Compose ($current) goes back." >&2
compose_put current.yml
# A Compose that named :latest (before decision 217) answers with whatever version it pulled.
if [[ "$current" =~ $VERSION_RE ]]; then previous=$current; else previous=""; fi
if deployed "Back: $target did not come up" && answers "$previous" 2>/dev/null; then
  echo "Back on $current; $target stays refused until a newer version comes out." >&2
else
  echo "Not even the previous Compose answered: fix it by hand (Dokploy, project Kaladrius)." >&2
fi
notify_monitor MONITOR_UPDATE_URL fail
exit 1

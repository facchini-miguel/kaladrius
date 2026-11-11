#!/bin/bash
# Pull the latest app and docs images and restart the stack when they differ from the ones
# last installed successfully. Runs every 5 minutes (systemd timer), so a failed update is
# retried on the next run. Use --force to restart even without a new image (and to try again
# an image that was refused).
#
# Automatic rollback (decision 135): after the restart the system must answer its health page
# within HEALTH_WAIT seconds. Otherwise the app image of the last successful update (tagged
# :previous) is put back, the new images are recorded as refused, so they are not tried again
# until a newer one is published, and the update monitor reports the failure until then.
set -euo pipefail
# This script decides the version itself, refusals included (common.sh).
UPDATING=1
source "$(dirname "$0")/common.sh"
# One run at a time: a manual --force waits for the timer's run instead of racing it.
exec 9>"$DIR/update.lock"
flock 9
# The state files below under the names of decision 147 before they are read (a no-op once done).
migrate_legacy_names
# The external monitor warns when updates fail or stop running (decision 079).
trap 'notify_monitor MONITOR_UPDATE_URL fail' ERR

case "${1:-}" in
  --force | --forcar) force=1 ;;
  *) force="" ;;
esac

# Removes by id the images in $1 that are not in $2 (ids separated by spaces or lines).
# Installed from the package, images are pulled by digest: an untagged one keeps that reference,
# is not "dangling", and prune never removes it. Refused while a container uses it; on Google
# Cloud prune already removed them.
remove_images() {
  local keep=" ${2//$'\n'/ } " image
  for image in $1; do
    case "$keep" in *" $image "*) continue ;; esac
    docker image rm "$image" >/dev/null 2>&1 || true
  done
}

# The new version did not come up: the previous app image goes back, with its Compose file and
# Caddyfile, so a new Caddy or PostgreSQL digest (decision 138) is undone too. The scripts stay
# those of the new version (this one included), so the refusal is kept on the next runs.
roll_back() {
  local before
  # The version refused before this one is not needed any more: only the last refusal is kept.
  before=$(cat "$REFUSED_IMAGE" 2>/dev/null || true)
  echo "$1" > "$REFUSED_IMAGE"
  echo "The system did not answer with the new version: going back to the previous one." >&2
  if ! docker image inspect "$PREVIOUS_APP_IMAGE" >/dev/null 2>&1; then
    echo "No previous version kept: fix it by hand." >&2
    end_maintenance
    notify_monitor MONITOR_UPDATE_URL fail
    exit 1
  fi
  APP_IMAGE="$PREVIOUS_APP_IMAGE"
  restore_compose_from "$PREVIOUS_APP_IMAGE" \
    || echo "Warning: no Compose file of the previous version; using the new one's." >&2
  compose up -d --remove-orphans
  reload_caddy
  remove_images "$before" "$1 $(docker image inspect --format '{{.Id}}' "$PREVIOUS_APP_IMAGE" 2>/dev/null || true)"
  if system_up; then
    echo "Back on the previous version; the new one stays refused until another comes out." >&2
  else
    echo "Not even the previous version answered: fix it by hand." >&2
  fi
  end_maintenance
  notify_monitor MONITOR_UPDATE_URL fail
  exit 1
}

registry_login
if ! installed_by_package; then
  docker pull -q "$APP_IMAGE" >/dev/null  # a failure tells the monitor (the ERR trap)
# Installed from the Linux package, an image already on the server is enough when the registry
# cannot be reached (an installation without internet, or a test image built there).
elif ! docker pull -q "$APP_IMAGE" >/dev/null 2>&1 && ! docker image inspect "$APP_IMAGE" >/dev/null 2>&1; then
  echo "Could not download $APP_IMAGE (no internet, or the registry is down)." >&2
  false  # the ERR trap tells the monitor
fi
images=("$APP_IMAGE")
# The documentation site (decision 067) never blocks an update of the system, and a package
# installation has none.
if [ -n "$DOCS_IMAGE" ]; then
  docker pull -q "$DOCS_IMAGE" >/dev/null 2>&1 || true
  images+=("$DOCS_IMAGE")
fi
current=$(docker image inspect --format '{{.Id}}' "${images[@]}" 2>/dev/null || true)
installed=$(cat "$INSTALLED_IMAGE" 2>/dev/null || true)
refused=$(cat "$REFUSED_IMAGE" 2>/dev/null || true)

# A server updated before decision 135 has no fallback yet: the image running now is the one
# installed last.
if [ "$current" = "$installed" ] && ! docker image inspect "$PREVIOUS_APP_IMAGE" >/dev/null 2>&1; then
  docker tag "$APP_IMAGE" "$PREVIOUS_APP_IMAGE"
fi

if [ -n "$refused" ] && [ "$current" = "$refused" ] && [ -z "$force" ]; then
  echo "The new version did not come up last time and is refused; the system stays on the previous one."
  notify_monitor MONITOR_UPDATE_URL fail
  exit 0
fi

if [ "$current" != "$installed" ] || [ -n "$force" ]; then
  extract_deploy_files
  source "$DIR/bin/common.sh"  # the helpers may have changed with the new image
  install_schedules
  if [ ! -f "$DIR/.env" ]; then
    echo "No $DIR/.env: configure the server before starting the system."
    exit 0
  fi
  # The app restarts: health.sh does not report the moment it is down (decision 209).
  begin_maintenance
  trap end_maintenance EXIT
  compose up -d --remove-orphans
  system_up || roll_back "$current"
  end_maintenance
  # Recorded only after the system answered: until then every run tries again.
  echo "$current" > "$INSTALLED_IMAGE"
  # The image :previous named until now and a refused one are not needed any more.
  old="$(docker image inspect --format '{{.Id}}' "$PREVIOUS_APP_IMAGE" 2>/dev/null || true) $refused"
  rm -f "$REFUSED_IMAGE"
  docker tag "$APP_IMAGE" "$PREVIOUS_APP_IMAGE"
  save_previous_compose
  docker image prune -f >/dev/null
  remove_images "$old" "$current"
  write_metrics update <<EOF
# HELP kaladrius_update_last_success_timestamp_seconds When the system was last updated.
# TYPE kaladrius_update_last_success_timestamp_seconds gauge
kaladrius_update_last_success_timestamp_seconds $(date +%s)
EOF
  echo "System updated: $(docker image inspect --format \
    '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}' "$APP_IMAGE")"
fi
notify_monitor MONITOR_UPDATE_URL

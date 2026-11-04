#!/bin/bash
# One-time move of a server installed before 0.26.1 from the "medical-system" names to
# "kaladrius" (decision 071): folder, systemd units, Compose project and volumes. The system
# is offline for about a minute. The old volumes stay as a copy until removed by hand:
#   docker volume rm medical-system_pgdata medical-system_caddy_data medical-system_caddy_config
# Run as root, with the new image already pulled (the update timer does it every 5 minutes):
#   docker run --rm --entrypoint cat <app image> /app/deploy/server/migrate_to_kaladrius.sh | sudo bash
set -euo pipefail
OLD=/opt/medical-system
NEW=/opt/kaladrius
APP_IMAGE=us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/app:latest

if [ -e "$NEW" ]; then
  echo "Nothing to do: $NEW already exists."
  exit 0
fi
if [ ! -d "$OLD" ]; then
  echo "Nothing to migrate: $OLD does not exist."
  exit 1
fi

# The volumes are copied with the database image the old stack ran, already on the server (only
# its shell is used). Read before anything stops.
copier=$(sed -n 's/^ *image: *\(postgres:[^ ]*\).*/\1/p' "$OLD/release/docker-compose.prod.yml")
if [ -z "$copier" ]; then
  echo "No PostgreSQL image in $OLD/release/docker-compose.prod.yml." >&2
  exit 1
fi

echo "== Stopping the scheduled tasks and the system"
systemctl stop medical-system-atualizar.timer medical-system-backup.timer \
  medical-system-saude.timer medical-system-atualizar.service medical-system-backup.service \
  medical-system-saude.service 2>/dev/null || true
docker compose -p medical-system -f "$OLD/release/docker-compose.prod.yml" down

echo "== $OLD -> $NEW"
mv "$OLD" "$NEW"

echo "== Copying the volumes (the old ones stay as a copy)"
for volume in pgdata caddy_data caddy_config; do
  docker volume create "kaladrius_$volume" >/dev/null
  docker run --rm --entrypoint sh -v "medical-system_$volume:/from:ro" \
    -v "kaladrius_$volume:/to" "$copier" -c 'cp -a /from/. /to/'
done

echo "== Replacing the systemd scheduled tasks"
systemctl disable medical-system-atualizar.timer medical-system-backup.timer \
  medical-system-saude.timer 2>/dev/null || true
mkdir -p "$NEW/legacy/units"
mv /etc/systemd/system/medical-system-* "$NEW/legacy/units/" 2>/dev/null || true
systemctl daemon-reload

echo "== Starting the system with the new names"
export MIGRATING=1
# shellcheck source=/dev/null
source /dev/stdin <<<"$(docker run --rm --entrypoint cat "$APP_IMAGE" /app/deploy/server/common.sh)"
rm -f "$INSTALLED_IMAGE"
extract_deploy_files
"$DIR/bin/update.sh" --force
systemctl list-timers 'kaladrius-*' --no-pager
echo "Migration finished."

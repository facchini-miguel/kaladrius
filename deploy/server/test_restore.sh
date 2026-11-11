#!/bin/bash
# Weekly restore test on the server (decision 079): downloads the newest backup, restores it
# into a throwaway PostgreSQL container and checks that the data is there. Nothing touches
# the system's database; the container and the file are removed at the end. Signals the
# external monitor (MONITOR_RESTORE_URL), or its failure.
set -euo pipefail
source "$(dirname "$0")/common.sh"
trap 'notify_monitor MONITOR_RESTORE_URL fail' ERR

CONTAINER=kaladrius-restore-test
API="https://storage.googleapis.com/storage/v1/b/$BACKUP_BUCKET/o"
work=$(mktemp -d)
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$work"' EXIT

if installed_by_package; then
  # The local folder of backup.sh (decision 140); the names sort by their timestamp. Read where
  # it is: a copy in /tmp (a small tmpfs on Debian 13) would not fit a big dump.
  object=$(find "$(backup_dir)" -maxdepth 1 -name 'kaladrius-*.dump' | sort | tail -1 || true)
  if [ -z "$object" ]; then
    # Installed less than two days ago (the setup finished, admin-created), before the first
    # daily backup: said plainly, not a failure. Later, no backup at all is a failure the monitor
    # hears (a disk no longer mounted, the dumps deleted).
    if [ ! -f "$DIR/admin-created" ] || [ -n "$(find "$DIR/admin-created" -mmin -2880)" ]; then
      echo "No backup in $(backup_dir) to test yet: the first one runs at 06:00 UTC (or now: sudo kaladrius backup)."
      exit 0
    fi
    echo "No backup in $(backup_dir): check the folder (a disk not mounted?) and sudo systemctl status kaladrius-backup.service." >&2
    false  # the ERR trap tells the monitor
  fi
  backup=$object
else
  token=$(google_token)
  # Newest by the timestamp in the name (kaladrius-YYYYMMDD-HHMMSS.dump).
  object=$(curl -sf -H "Authorization: Bearer $token" "$API?fields=items(name)" \
    | grep -o '"name": *"[^"]*\.dump"' | sed -E 's/.*"([^"]*)"$/\1/' \
    | sed -E 's/.*-([0-9]{8}-[0-9]{6})\.dump$/\1 &/' | sort | tail -1 | cut -d' ' -f2)
  [ -n "$object" ]
  backup="$work/backup.dump"
  curl -sf -H "Authorization: Bearer $token" "$API/$object?alt=media" -o "$backup"
fi
echo "Backup: $object ($(du -h "$backup" | cut -f1))"

# A small container: the e2-micro has 1 GB of RAM and the system keeps running. The image of
# production's database, digest included (decision 138).
docker run -d --rm --name "$CONTAINER" --memory 256m -e POSTGRES_PASSWORD=test \
  "$(postgres_image)" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$CONTAINER" pg_isready -U postgres -q 2>/dev/null && break
  sleep 1
done
sleep 3  # the image restarts the server once after the first initialization
for _ in $(seq 1 60); do
  docker exec "$CONTAINER" pg_isready -U postgres -q 2>/dev/null && break
  sleep 1
done
docker exec "$CONTAINER" createdb -U postgres restored
docker cp "$backup" "$CONTAINER:/backup.dump"
docker exec "$CONTAINER" pg_restore -U postgres -d restored --no-owner --no-privileges \
  --exit-on-error /backup.dump

# The restored database has the migrations of every app and the clinic. Google Cloud always has
# one. A package installation has none until "Primeiros passos", so there the clinic is required
# when the system's database has one: it is read for that count only, and only when it is
# running (a stopped system does not make a good backup fail its test). When it runs, the count
# must succeed: a failed query never skips the check. One check per line: a failing
# `[ a ] && [ b ]` does not stop a `set -e` script.
# A backup from before 0.59.0 still has the Portuguese table (decision 179).
clinics=$(docker exec "$CONTAINER" psql -U postgres -d restored -tAc "SELECT (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM ' || coalesce(to_regclass('core_clinic'), to_regclass('core_clinica'))::text, false, true, '')))[1]::text")
migrations=$(docker exec "$CONTAINER" psql -U postgres -d restored -tAc "SELECT count(*) FROM django_migrations")
require_clinic=$(installed_by_package || echo 1)
if service_running db; then
  in_system=$(compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM core_clinic"' </dev/null)
  echo "Restored: $clinics clinic(s), $migrations migrations (the system has $in_system clinic(s))."
  if [ "$in_system" -ge 1 ]; then require_clinic=1; fi
else
  echo "Restored: $clinics clinic(s), $migrations migrations (the system is stopped: clinics not compared)."
fi
[ "$migrations" -ge 1 ]
if [ -n "$require_clinic" ]; then
  [ "$clinics" -ge 1 ]
fi

write_metrics restore_test <<EOF
# HELP kaladrius_restore_test_last_success_timestamp_seconds When the last restore test passed.
# TYPE kaladrius_restore_test_last_success_timestamp_seconds gauge
kaladrius_restore_test_last_success_timestamp_seconds $(date +%s)
EOF
notify_monitor MONITOR_RESTORE_URL
echo "Restore test finished."

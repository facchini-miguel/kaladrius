#!/bin/bash
# Daily database dump. On Google Cloud, to Cloud Storage (bucket in the free-tier region;
# objects are encrypted at rest by Google and deleted automatically after 30 days). Installed
# from the Linux package (decision 140), to a local folder, KALADRIUS_BACKUP_DIR
# (/var/backups/kaladrius), keeping KALADRIUS_BACKUP_DAYS days (14): copy that folder to
# another disk or computer, since a backup on the same disk does not survive the disk.
set -euo pipefail
source "$(dirname "$0")/common.sh"
# The external monitor hears about a failed backup at once, and about a missing one when
# today's signal does not arrive (decision 078).
trap 'notify_monitor MONITOR_BACKUP_URL fail' ERR

name="kaladrius-$(date -u +%Y%m%d-%H%M%S).dump"
if installed_by_package; then
  dir=$(backup_dir)
  days=$(env_value KALADRIUS_BACKUP_DAYS)
  mkdir -p "$dir"
  chmod 700 "$dir"
  # Written in the backup folder itself and renamed when complete: never through /tmp (a tmpfs
  # of half the RAM on Debian 13, smaller than a big dump), and written to disk once.
  file=$(mktemp "$dir/.$name.XXXXXX")
else
  file=$(mktemp)
fi
trap 'rm -f "$file"' EXIT
compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$file"
size=$(stat -c %s "$file")
readable=$(du -h "$file" | cut -f1)
if installed_by_package; then
  mv -f "$file" "$dir/$name"
  # The old backups, and a dump left half-written by a server that went down in the middle.
  find "$dir" -maxdepth 1 \( -name 'kaladrius-*.dump' -mtime +"${days:-14}" \
    -o -name '.kaladrius-*.dump.*' -mmin +1440 \) -delete
  echo "Backup saved: $dir/$name ($readable)"
else
  # --upload-file streams the dump instead of loading it into memory (the VM has 1 GB).
  curl -sf -X POST \
    -H "Authorization: Bearer $(google_token)" \
    -H "Content-Type: application/octet-stream" \
    --upload-file "$file" \
    "https://storage.googleapis.com/upload/storage/v1/b/$BACKUP_BUCKET/o?uploadType=media&name=$name" >/dev/null
  echo "Backup uploaded: gs://$BACKUP_BUCKET/$name ($readable)"
fi

# Recorded in the database: superusers see a warning in the web app when backups stop.
compose exec -T app python manage.py registrar_backup "$name" "$size" \
  || echo "Warning: backup made, but it could not be recorded in the system."

# Daily retention: failed login records older than 30 days are deleted (decision 045).
compose exec -T app python manage.py aplicar_retencao \
  || echo "Warning: the old records could not be deleted."

notify_monitor MONITOR_BACKUP_URL

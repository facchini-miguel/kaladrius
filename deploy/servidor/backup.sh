#!/bin/bash
# Daily database dump. On Google Cloud, to Cloud Storage (bucket in the free-tier region;
# objects are encrypted at rest by Google and deleted automatically after 30 days). Installed
# from the Linux package (decision 140), to a local folder, KALADRIUS_BACKUP_PASTA
# (/var/backups/kaladrius), keeping KALADRIUS_BACKUP_DIAS days (14): copy that folder to
# another disk or computer, since a backup on the same disk does not survive the disk.
set -euo pipefail
source "$(dirname "$0")/comum.sh"
# The external monitor hears about a failed backup at once, and about a missing one when
# today's signal does not arrive (decision 078).
trap 'avisar_monitor MONITOR_BACKUP_URL fail' ERR

nome="kaladrius-$(date -u +%Y%m%d-%H%M%S).dump"
arquivo=$(mktemp)
trap 'rm -f "$arquivo"' EXIT
compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$arquivo"
if instalado_por_pacote; then
  pasta=$(valor_do_env KALADRIUS_BACKUP_PASTA)
  pasta=${pasta:-/var/backups/kaladrius}
  dias=$(valor_do_env KALADRIUS_BACKUP_DIAS)
  mkdir -p "$pasta"
  chmod 700 "$pasta"
  install -m 600 "$arquivo" "$pasta/$nome"
  find "$pasta" -maxdepth 1 -name 'kaladrius-*.dump' -mtime +"${dias:-14}" -delete
  echo "Backup salvo: $pasta/$nome ($(du -h "$arquivo" | cut -f1))"
else
  # --upload-file streams the dump instead of loading it into memory (the VM has 1 GB).
  curl -sf -X POST \
    -H "Authorization: Bearer $(token_google)" \
    -H "Content-Type: application/octet-stream" \
    --upload-file "$arquivo" \
    "https://storage.googleapis.com/upload/storage/v1/b/$BUCKET_BACKUP/o?uploadType=media&name=$nome" >/dev/null
  echo "Backup enviado: gs://$BUCKET_BACKUP/$nome ($(du -h "$arquivo" | cut -f1))"
fi

# Recorded in the database: superusers see a warning in the web app when backups stop.
compose exec -T app python manage.py registrar_backup "$nome" "$(stat -c %s "$arquivo")" \
  || echo "Aviso: backup enviado, mas não foi possível registrá-lo no sistema."

# Daily retention: failed login records older than 30 days are deleted (decision 045).
compose exec -T app python manage.py aplicar_retencao \
  || echo "Aviso: não foi possível apagar os registros antigos."

avisar_monitor MONITOR_BACKUP_URL

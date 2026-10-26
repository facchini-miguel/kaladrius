#!/bin/bash
# Daily database dump to Cloud Storage (bucket in the free-tier region; objects are
# encrypted at rest by Google and deleted automatically after 30 days).
set -euo pipefail
source "$(dirname "$0")/comum.sh"

nome="medical-system-$(date -u +%Y%m%d-%H%M%S).dump"
arquivo=$(mktemp)
trap 'rm -f "$arquivo"' EXIT
compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$arquivo"
curl -sf -X POST \
  -H "Authorization: Bearer $(token_google)" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @"$arquivo" \
  "https://storage.googleapis.com/upload/storage/v1/b/$BUCKET_BACKUP/o?uploadType=media&name=$nome" >/dev/null
echo "Backup enviado: gs://$BUCKET_BACKUP/$nome ($(du -h "$arquivo" | cut -f1))"

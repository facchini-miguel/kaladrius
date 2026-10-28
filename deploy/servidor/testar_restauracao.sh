#!/bin/bash
# Weekly restore test on the server (decision 079): downloads the newest backup, restores it
# into a throwaway PostgreSQL container and checks that the data is there. Nothing touches
# the system's database; the container and the file are removed at the end. Signals the
# external monitor (MONITOR_RESTAURACAO_URL), or its failure.
set -euo pipefail
source "$(dirname "$0")/comum.sh"
trap 'avisar_monitor MONITOR_RESTAURACAO_URL fail' ERR

CONTAINER=kaladrius-teste-restauracao
API="https://storage.googleapis.com/storage/v1/b/$BUCKET_BACKUP/o"
pasta=$(mktemp -d)
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$pasta"' EXIT

token=$(token_google)
# Newest by the timestamp in the name (kaladrius-YYYYMMDD-HHMMSS.dump).
objeto=$(curl -sf -H "Authorization: Bearer $token" "$API?fields=items(name)" \
  | grep -o '"name": *"[^"]*\.dump"' | sed -E 's/.*"([^"]*)"$/\1/' \
  | sed -E 's/.*-([0-9]{8}-[0-9]{6})\.dump$/\1 &/' | sort | tail -1 | cut -d' ' -f2)
[ -n "$objeto" ]
curl -sf -H "Authorization: Bearer $token" "$API/$objeto?alt=media" -o "$pasta/backup.dump"
echo "Backup: $objeto ($(du -h "$pasta/backup.dump" | cut -f1))"

# A small container: the e2-micro has 1 GB of RAM and the system keeps running.
docker run -d --rm --name "$CONTAINER" --memory 256m -e POSTGRES_PASSWORD=teste \
  postgres:16-alpine >/dev/null
for _ in $(seq 1 60); do
  docker exec "$CONTAINER" pg_isready -U postgres -q 2>/dev/null && break
  sleep 1
done
sleep 3  # the image restarts the server once after the first initialization
for _ in $(seq 1 60); do
  docker exec "$CONTAINER" pg_isready -U postgres -q 2>/dev/null && break
  sleep 1
done
docker exec "$CONTAINER" createdb -U postgres restaurado
docker cp "$pasta/backup.dump" "$CONTAINER:/backup.dump"
docker exec "$CONTAINER" pg_restore -U postgres -d restaurado --no-owner --no-privileges \
  --exit-on-error /backup.dump

# The restored database has the clinic and the migrations of every app.
clinicas=$(docker exec "$CONTAINER" psql -U postgres -d restaurado -tAc "SELECT count(*) FROM core_clinica")
migracoes=$(docker exec "$CONTAINER" psql -U postgres -d restaurado -tAc "SELECT count(*) FROM django_migrations")
echo "Restaurado: $clinicas clínica(s), $migracoes migrações."
[ "$clinicas" -ge 1 ] && [ "$migracoes" -ge 1 ]

avisar_monitor MONITOR_RESTAURACAO_URL
echo "Teste de restauração concluído."

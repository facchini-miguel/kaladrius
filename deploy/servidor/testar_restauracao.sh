#!/bin/bash
# Weekly restore test on the server (decision 079): downloads the newest backup, restores it
# into a throwaway PostgreSQL container and checks that the data is there. Nothing touches
# the system's database; the container and the file are removed at the end. Signals the
# external monitor (MONITOR_RESTAURACAO_URL), or its failure.
set -euo pipefail
source "$(dirname "$0")/comum.sh"
trap 'avisar_monitor MONITOR_RESTAURACAO_URL fail' ERR
# After a rollback, the PostgreSQL of the version running (comum.sh).
if na_versao_anterior; then usar_a_versao_anterior; fi

CONTAINER=kaladrius-teste-restauracao
API="https://storage.googleapis.com/storage/v1/b/$BUCKET_BACKUP/o"
pasta=$(mktemp -d)
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$pasta"' EXIT

if instalado_por_pacote; then
  # The local folder of backup.sh (decision 140); the names sort by their timestamp. Read where
  # it is: a copy in /tmp (a small tmpfs on Debian 13) would not fit a big dump.
  local_backups=$(valor_do_env KALADRIUS_BACKUP_PASTA)
  objeto=$(find "${local_backups:-/var/backups/kaladrius}" -maxdepth 1 -name 'kaladrius-*.dump' \
    | sort | tail -1)
  [ -n "$objeto" ]
  backup=$objeto
else
  token=$(token_google)
  # Newest by the timestamp in the name (kaladrius-YYYYMMDD-HHMMSS.dump).
  objeto=$(curl -sf -H "Authorization: Bearer $token" "$API?fields=items(name)" \
    | grep -o '"name": *"[^"]*\.dump"' | sed -E 's/.*"([^"]*)"$/\1/' \
    | sed -E 's/.*-([0-9]{8}-[0-9]{6})\.dump$/\1 &/' | sort | tail -1 | cut -d' ' -f2)
  [ -n "$objeto" ]
  backup="$pasta/backup.dump"
  curl -sf -H "Authorization: Bearer $token" "$API/$objeto?alt=media" -o "$backup"
fi
echo "Backup: $objeto ($(du -h "$backup" | cut -f1))"

# A small container: the e2-micro has 1 GB of RAM and the system keeps running. The image of
# production's database, digest included (decision 138).
docker run -d --rm --name "$CONTAINER" --memory 256m -e POSTGRES_PASSWORD=teste \
  "$(imagem_postgres)" >/dev/null
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
docker cp "$backup" "$CONTAINER:/backup.dump"
docker exec "$CONTAINER" pg_restore -U postgres -d restaurado --no-owner --no-privileges \
  --exit-on-error /backup.dump

# The restored database has the migrations of every app and, when the system has a clinic
# (a new installation has none until "Primeiros passos"), the clinic. The system's database is
# only read for that count, and only when it is running: a stopped system does not make a good
# backup fail its test. One check per line: a failing `[ a ] && [ b ]` does not stop a `set -e`
# script.
clinicas=$(docker exec "$CONTAINER" psql -U postgres -d restaurado -tAc "SELECT count(*) FROM core_clinica")
migracoes=$(docker exec "$CONTAINER" psql -U postgres -d restaurado -tAc "SELECT count(*) FROM django_migrations")
no_sistema=$(compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM core_clinica"' </dev/null 2>/dev/null || true)
if [ -n "$no_sistema" ]; then
  echo "Restaurado: $clinicas clínica(s), $migracoes migrações (o sistema tem $no_sistema clínica(s))."
else
  no_sistema=0
  echo "Restaurado: $clinicas clínica(s), $migracoes migrações (o sistema está parado: sem comparar as clínicas)."
fi
[ "$migracoes" -ge 1 ]
if [ "$no_sistema" -ge 1 ]; then
  [ "$clinicas" -ge 1 ]
fi

avisar_monitor MONITOR_RESTAURACAO_URL
echo "Teste de restauração concluído."

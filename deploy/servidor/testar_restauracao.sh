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

if instalado_por_pacote; then
  # The local folder of backup.sh (decision 140); the names sort by their timestamp. Read where
  # it is: a copy in /tmp (a small tmpfs on Debian 13) would not fit a big dump.
  objeto=$(find "$(pasta_dos_backups)" -maxdepth 1 -name 'kaladrius-*.dump' \
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

# The restored database has the migrations of every app and the clinic. Google Cloud always has
# one. A package installation has none until "Primeiros passos", so there the clinic is required
# when the system's database has one: it is read for that count only, and only when it is
# running (a stopped system does not make a good backup fail its test). When it runs, the count
# must succeed: a failed query never skips the check. One check per line: a failing
# `[ a ] && [ b ]` does not stop a `set -e` script.
clinicas=$(docker exec "$CONTAINER" psql -U postgres -d restaurado -tAc "SELECT count(*) FROM core_clinica")
migracoes=$(docker exec "$CONTAINER" psql -U postgres -d restaurado -tAc "SELECT count(*) FROM django_migrations")
exigir_clinica=$(instalado_por_pacote || echo 1)
# grep without -q (it reads all its input): an early exit would fail the pipeline (pipefail).
if compose ps --status running --services 2>/dev/null | grep -x db >/dev/null; then
  no_sistema=$(compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM core_clinica"' </dev/null)
  echo "Restaurado: $clinicas clínica(s), $migracoes migrações (o sistema tem $no_sistema clínica(s))."
  if [ "$no_sistema" -ge 1 ]; then exigir_clinica=1; fi
else
  echo "Restaurado: $clinicas clínica(s), $migracoes migrações (o sistema está parado: sem comparar as clínicas)."
fi
[ "$migracoes" -ge 1 ]
if [ -n "$exigir_clinica" ]; then
  [ "$clinicas" -ge 1 ]
fi

avisar_monitor MONITOR_RESTAURACAO_URL
echo "Teste de restauração concluído."

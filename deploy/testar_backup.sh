#!/bin/bash
# Restore test: downloads a backup from Cloud Storage, restores it into a throwaway
# PostgreSQL container on this machine and prints what is inside. Nothing touches the
# server or the local development database; the container and the file are removed at the
# end. Usage (on your machine, with gcloud and Docker):
#   deploy/testar_backup.sh                 # newest backup
#   deploy/testar_backup.sh <object name>   # a specific one
set -euo pipefail

BUCKET=medical-system-facchini-backups
CONTAINER=medical-system-teste-backup
pasta=$(mktemp -d)
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$pasta"' EXIT

objeto=${1:-$(gcloud storage ls "gs://$BUCKET/" | sort | tail -1)}
objeto=${objeto#gs://$BUCKET/}
echo "Backup: gs://$BUCKET/$objeto"
gcloud storage cp --quiet "gs://$BUCKET/$objeto" "$pasta/backup.dump"
echo "Tamanho: $(du -h "$pasta/backup.dump" | cut -f1)"

docker run -d --rm --name "$CONTAINER" -e POSTGRES_PASSWORD=teste postgres:16-alpine >/dev/null
until docker exec "$CONTAINER" pg_isready -U postgres -q; do sleep 1; done
sleep 2  # the image restarts the server once after the first initialization
until docker exec "$CONTAINER" pg_isready -U postgres -q; do sleep 1; done
docker exec "$CONTAINER" createdb -U postgres restaurado
docker cp "$pasta/backup.dump" "$CONTAINER:/backup.dump"
# --exit-on-error: any problem in the dump fails the test.
docker exec "$CONTAINER" pg_restore -U postgres -d restaurado --no-owner --no-privileges \
  --exit-on-error /backup.dump
echo "Restauração concluída sem erros."

docker exec -i "$CONTAINER" psql -U postgres -d restaurado -q -A -t -F ' | ' <<'SQL'
\echo
\echo 'Tabela | registros'
SELECT t, (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM ' || t, false, true, '')))[1]::text
FROM unnest(ARRAY[
  'core_clinica', 'core_usuario', 'core_vinculo', 'pacientes_paciente', 'profissionais_profissional',
  'agenda_agendamento', 'rechamadas_rechamada', 'financeiro_lancamento', 'financeiro_pagamento',
  'financeiro_caixa', 'auditoria_registroauditoria', 'core_backup'
]) AS t
WHERE to_regclass(t) IS NOT NULL;
\echo
\echo 'Última migração de cada app'
SELECT app || ' | ' || max(name) FROM django_migrations
WHERE app IN ('core', 'pacientes', 'agenda', 'financeiro') GROUP BY app ORDER BY app;
SQL

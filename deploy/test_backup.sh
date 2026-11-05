#!/bin/bash
# Restore test: downloads a backup from Cloud Storage, restores it into a throwaway
# PostgreSQL container on this machine and prints what is inside. Nothing touches the
# server or the local development database; the container and the file are removed at the
# end. Usage (on your machine, with gcloud and Docker):
#   deploy/test_backup.sh                 # newest backup
#   deploy/test_backup.sh <object name>   # a specific one
set -euo pipefail

BUCKET=kaladrius-backups
# The image of production's database, digest included (decision 138).
COMPOSE_PROD="$(cd "$(dirname "$0")" && pwd)/docker-compose.prod.yml"
IMAGE=$(sed -n 's/^ *image: *\(postgres:[^ ]*\).*/\1/p' "$COMPOSE_PROD")
[ -n "$IMAGE" ] || { echo "No PostgreSQL image in $COMPOSE_PROD." >&2; exit 1; }
CONTAINER=kaladrius-backup-test
work=$(mktemp -d)
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$work"' EXIT

# Newest by the timestamp in the name (older backups start with medical-system-, newer with kaladrius-).
object=${1:-$(gcloud storage ls "gs://$BUCKET/" | sed -E 's/.*-([0-9]{8}-[0-9]{6})\.dump$/\1 &/' | sort | tail -1 | cut -d' ' -f2)}
object=${object#gs://$BUCKET/}
echo "Backup: gs://$BUCKET/$object"
gcloud storage cp --quiet "gs://$BUCKET/$object" "$work/backup.dump"
echo "Size: $(du -h "$work/backup.dump" | cut -f1)"

docker run -d --rm --name "$CONTAINER" -e POSTGRES_PASSWORD=test "$IMAGE" >/dev/null
until docker exec "$CONTAINER" pg_isready -U postgres -q; do sleep 1; done
sleep 2  # the image restarts the server once after the first initialization
until docker exec "$CONTAINER" pg_isready -U postgres -q; do sleep 1; done
docker exec "$CONTAINER" createdb -U postgres restored
docker cp "$work/backup.dump" "$CONTAINER:/backup.dump"
# --exit-on-error: any problem in the dump fails the test.
docker exec "$CONTAINER" pg_restore -U postgres -d restored --no-owner --no-privileges \
  --exit-on-error /backup.dump
echo "Restore finished with no errors."

docker exec -i "$CONTAINER" psql -U postgres -d restored -q -A -t -F ' | ' <<'SQL'
\echo
\echo 'Table | rows'
SELECT t, (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM ' || t, false, true, '')))[1]::text
FROM unnest(ARRAY[
  'core_clinica', 'core_usuario', 'core_vinculo', 'pacientes_paciente', 'profissionais_profissional',
  'agenda_agendamento', 'rechamadas_rechamada', 'financeiro_lancamento', 'financeiro_pagamento',
  'financeiro_caixa', 'financeiro_comissao', 'financeiro_transacaobancaria', 'orcamentos_orcamento', 'auditoria_registroauditoria', 'core_backup',
  -- the same tables with their names since 0.59.0 (decision 179); a backup has one or the other
  'core_clinic', 'core_user', 'core_membership', 'patients_patient', 'practitioners_practitioner',
  'schedule_appointment', 'recalls_recall', 'finance_entry', 'finance_payment',
  'finance_cash_register', 'finance_commission', 'finance_bank_transaction', 'estimates_estimate', 'audit_entry'
]) AS t
WHERE to_regclass(t) IS NOT NULL;
\echo
\echo 'Last migration of each app'
SELECT app || ' | ' || max(name) FROM django_migrations
WHERE app IN ('core', 'pacientes', 'agenda', 'financeiro', 'orcamentos') GROUP BY app ORDER BY app;
SQL

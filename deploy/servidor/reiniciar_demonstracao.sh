#!/bin/bash
# Nightly reset of the public demo (decision 086). Only on a server with
# DJANGO_DEMONSTRACAO=1 in .env; anywhere else it does nothing.
#
#   reiniciar_demonstracao.sh --salvar-base   keep the current database as the demo's base
#   reiniciar_demonstracao.sh                 restore the base and move its dates forward
#
# Restoring drops what visitors changed (and any later change by the owner: save the base
# again after one). The dates move by whole weeks since the base was saved, so the schedule
# always looks current and each appointment keeps its weekday. The backups list
# (core_backup) is real, so it is kept as it is.
set -euo pipefail
source "$(dirname "$0")/comum.sh"

if [ "$(valor_do_env DJANGO_DEMONSTRACAO)" != "1" ]; then
  echo "Este não é o servidor de demonstração (DJANGO_DEMONSTRACAO=1): nada a fazer."
  exit 0
fi
trap 'avisar_monitor MONITOR_DEMONSTRACAO_URL fail' ERR

PASTA="$DIR/demonstracao"
BASE="$PASTA/base.dump"
DATA_DA_BASE="$PASTA/base-data"
mkdir -p "$PASTA"

banco() {  # run a command in the database container with the app's credentials
  compose exec -T db sh -c "$1"
}

if [ "${1:-}" = "--salvar-base" ]; then
  banco 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" --exclude-table-data=core_backup --exclude-table-data=django_session --exclude-table-data="axes_*"' > "$BASE.novo"
  mv -f "$BASE.novo" "$BASE"
  date +%F > "$DATA_DA_BASE"
  echo "Base da demonstração salva: $BASE ($(du -h "$BASE" | cut -f1)), datas de $(cat "$DATA_DA_BASE")."
  exit 0
fi

[ -s "$BASE" ] || { echo "Sem base: rode antes $0 --salvar-base" >&2; exit 1; }

backups=$(mktemp)
# Whatever happens, the app comes back up (an empty or partial database is still better
# than a site that is down; the next night tries again).
trap 'rm -f "$backups"; compose start app >/dev/null 2>&1 || true' EXIT
sql() {  # run SQL read from stdin
  banco 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q -v ON_ERROR_STOP=1'
}
banco 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "\copy core_backup TO STDOUT"' > "$backups"

compose stop app
# A clean schema: tables created by later versions are not left behind; the app's migrate
# creates them again when it starts.
sql <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
SQL
banco 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error' < "$BASE"
banco 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "\copy core_backup FROM STDIN"' < "$backups"
sql <<'SQL'
SELECT setval(pg_get_serial_sequence('core_backup', 'id'), COALESCE(MAX(id), 1)) FROM core_backup;
SQL
compose start app

# The app applies pending migrations when it starts; wait until there are none left.
for _ in $(seq 1 60); do
  compose exec -T app python manage.py migrate --check >/dev/null 2>&1 && break
  sleep 5
done
compose exec -T app python manage.py avancar_datas --desde "$(cat "$DATA_DA_BASE")" --confirmar

avisar_monitor MONITOR_DEMONSTRACAO_URL
echo "Demonstração reiniciada."

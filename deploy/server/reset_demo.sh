#!/bin/bash
# Nightly reset of the public demo (decision 086). Only on a server with
# DJANGO_DEMO=1 in .env; anywhere else it does nothing.
#
#   reset_demo.sh --save-base   keep the current database as the demo's base
#   reset_demo.sh               restore the base and move its dates forward
#
# Restoring drops what visitors changed (and any later change by the owner: save the base
# again after one). The dates move by whole weeks since the base was saved, so the schedule
# always looks current and each appointment keeps its weekday. The backups list
# (core_backup) is real, so it is kept as it is, and so are the accounts of the system
# administrators (superusers): password, e-mail, language, two-step verification and recovery
# codes go back to what they were before the reset (decision 118), or the owner would lose
# them every night.
set -euo pipefail
source "$(dirname "$0")/common.sh"

if [ "$(env_value DJANGO_DEMO)" != "1" ]; then
  echo "This is not the demo server (DJANGO_DEMO=1): nothing to do."
  exit 0
fi
trap 'notify_monitor MONITOR_DEMO_URL fail' ERR

DEMO_DIR="$DIR/demo"
BASE="$DEMO_DIR/base.dump"
BASE_DATE="$DEMO_DIR/base-date"
mkdir -p "$DEMO_DIR"

db() {  # run a command in the database container with the app's credentials
  compose exec -T db sh -c "$1"
}

case "${1:-}" in --save-base | --salvar-base) save_base=1 ;; *) save_base="" ;; esac
if [ -n "$save_base" ]; then
  db 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" --exclude-table-data=core_backup --exclude-table-data=django_session --exclude-table-data="axes_*"' > "$BASE.new"
  mv -f "$BASE.new" "$BASE"
  date +%F > "$BASE_DATE"
  echo "Demo base saved: $BASE ($(du -h "$BASE" | cut -f1)), dates of $(cat "$BASE_DATE")."
  exit 0
fi

[ -s "$BASE" ] || { echo "No base: run $0 --save-base first" >&2; exit 1; }
started=$(date +%s)

backups=$(mktemp)
# Whatever happens, the app comes back up (an empty or partial database is still better
# than a site that is down; the next night tries again).
trap 'rm -f "$backups"; compose start app >/dev/null 2>&1 || true' EXIT
sql() {  # run SQL read from stdin
  db 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q -v ON_ERROR_STOP=1'
}
db 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "\copy core_backup TO STDOUT"' > "$backups"

# The system administrators' accounts (decision 118). A table that does not exist yet (an
# older version) just leaves its file empty.
accounts=$(mktemp -d)
trap 'rm -rf "$backups" "$accounts"; compose start app >/dev/null 2>&1 || true; end_maintenance' EXIT
keep() {  # keep <file> <query>; \copy takes one line, so the query is joined first
  local query="${2//$'\n'/ }"
  db "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -qc \"\\copy ($query) TO STDOUT\"" \
    >"$accounts/$1" 2>/dev/null || : >"$accounts/$1"
}
keep users "SELECT username, password, email, language FROM core_user WHERE is_superuser"
keep two_factor "SELECT u.username, d.secret, d.active, d.activated_at, d.last_step
  FROM account_two_factor d JOIN core_user u ON u.id = d.user_id WHERE u.is_superuser"
keep codes "SELECT u.username, c.digest, c.used_at
  FROM account_recovery_code c JOIN core_user u ON u.id = c.user_id WHERE u.is_superuser"

# The site is down until the migrations finish: health.sh does not report it (decision 209).
begin_maintenance
stopped=$(date +%s)
compose stop app
# A clean schema: tables created by later versions are not left behind; the app's migrate
# creates them again when it starts.
sql <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
SQL
db 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error' < "$BASE"
compose start app

# The app applies pending migrations when it starts; wait until there are none left. Only
# then is the schema today's, whatever version saved the base (decision 179): what was kept
# goes back after it.
for _ in $(seq 1 60); do
  compose exec -T app python manage.py migrate --check >/dev/null 2>&1 && break
  sleep 5
done
end_maintenance
back=$(date +%s)
sql <<'SQL'
TRUNCATE core_backup;
SQL
db 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "\copy core_backup FROM STDIN"' < "$backups"
sql <<'SQL'
SELECT setval(pg_get_serial_sequence('core_backup', 'id'), COALESCE(MAX(id), 1)) FROM core_backup;
SQL
# The system administrators get their accounts back (decision 118), matched by username.
sql <<'SQL'
CREATE TABLE _kept_users (username text, password text, email text, language text);
CREATE TABLE _kept_two_factor (
  username text, secret text, active boolean, activated_at timestamptz, last_step bigint
);
CREATE TABLE _kept_codes (username text, digest text, used_at timestamptz);
SQL
for table in users two_factor codes; do
  db "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -qc \"\\copy _kept_$table FROM STDIN\"" \
    <"$accounts/$table"
done
sql <<'SQL'
UPDATE core_user u SET password = g.password, email = g.email, language = g.language
  FROM _kept_users g WHERE u.username = g.username;
DELETE FROM account_two_factor WHERE user_id IN
  (SELECT u.id FROM core_user u JOIN _kept_users g USING (username));
INSERT INTO account_two_factor (secret, active, activated_at, last_step, user_id)
  SELECT d.secret, d.active, d.activated_at, d.last_step, u.id
  FROM _kept_two_factor d JOIN core_user u USING (username);
DELETE FROM account_recovery_code WHERE user_id IN
  (SELECT u.id FROM core_user u JOIN _kept_users g USING (username));
INSERT INTO account_recovery_code (digest, used_at, user_id)
  SELECT c.digest, c.used_at, u.id FROM _kept_codes c JOIN core_user u USING (username);
DROP TABLE _kept_users, _kept_two_factor, _kept_codes;
SQL

since=$(cat "$BASE_DATE")
manage advance_dates --since "$since" --confirm -- avancar_datas --desde "$since" --confirmar

write_metrics demo_reset <<EOF
# HELP kaladrius_demo_reset_last_success_timestamp_seconds When the last nightly demo reset finished.
# TYPE kaladrius_demo_reset_last_success_timestamp_seconds gauge
kaladrius_demo_reset_last_success_timestamp_seconds $(date +%s)
# HELP kaladrius_demo_reset_duration_seconds How long the last demo reset took.
# TYPE kaladrius_demo_reset_duration_seconds gauge
kaladrius_demo_reset_duration_seconds $(($(date +%s) - started))
# HELP kaladrius_demo_reset_downtime_seconds How long the demo was down in the last reset.
# TYPE kaladrius_demo_reset_downtime_seconds gauge
kaladrius_demo_reset_downtime_seconds $((back - stopped))
EOF
notify_monitor MONITOR_DEMO_URL
echo "Demo reset."

---
sidebar_position: 2
title: Backup and restore
---

# Backup and restore

The whole system is in the PostgreSQL database: patients, schedule, finance, users and the audit log. A backup is a `pg_dump` of it. **A backup only counts if it restores**: test it from time to time.

## Google Cloud installation

Already set up: every day at 06:00 UTC the dump goes to the Cloud Storage bucket, and each object is deleted after 30 days. If it fails, it is retried every 20 minutes (up to 4 times in 3 hours). Each successful backup is recorded in the system; when the last one is older than 26 hours, superusers see a warning at the top of every page.

```bash
sudo /opt/kaladrius/bin/backup.sh                       # on the VM: back up now
gcloud storage ls -l gs://<bucket>/                         # on your computer: list
```

## Own server

Create `/opt/kaladrius/backup.sh`:

```bash
#!/bin/bash
# Daily database backup, kept for 30 days and recorded in the system.
set -euo pipefail
K="docker compose -p kaladrius --env-file /opt/kaladrius/.env -f /opt/kaladrius/deploy/docker-compose.prod.yml"
PASTA=/var/backups/kaladrius
mkdir -p "$PASTA" && chmod 700 "$PASTA"
nome="kaladrius-$(date -u +%Y%m%d-%H%M%S).dump"
$K exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$PASTA/$nome"
$K exec -T app python manage.py registrar_backup "$nome" "$(stat -c %s "$PASTA/$nome")"
$K exec -T app python manage.py aplicar_retencao
find "$PASTA" -name 'kaladrius-*.dump' -mtime +30 -delete
```

Schedule it every day at 3 a.m.:

```bash
sudo chmod 700 /opt/kaladrius/backup.sh
echo '0 3 * * * root /opt/kaladrius/backup.sh >> /var/log/kaladrius-backup.log 2>&1' | sudo tee /etc/cron.d/kaladrius-backup
```

- `registrar_backup` records the backup, so the warning for superusers works.
- `aplicar_retencao` deletes refused login attempts older than 30 days (privacy policy).

:::warning
A backup on the same disk does not survive the loss of the server. Copy `/var/backups/kaladrius` to somewhere else every day: another server, an object storage (S3, Backblaze B2, Google Cloud Storage) with `rclone`, or an encrypted external disk. The files contain patient data: keep them private and encrypted.
:::

## Restore

:::danger
Restoring **replaces** the current database with the backup. Everything recorded after the backup is lost.
:::

```bash
# Own server
kaladrius exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < /var/backups/kaladrius/<file>.dump
kaladrius restart app

# Google Cloud, on the VM
gcloud storage cp gs://<bucket>/<file>.dump /tmp/restaurar.dump
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restaurar.dump
```

## Test a backup without touching the server

Restore it into a throwaway PostgreSQL on any computer with Docker, and look at what is inside:

```bash
docker run -d --rm --name teste-backup -e POSTGRES_PASSWORD=teste postgres:16-alpine
sleep 5
docker exec teste-backup createdb -U postgres restaurado
docker cp <file>.dump teste-backup:/backup.dump
docker exec teste-backup pg_restore -U postgres -d restaurado --no-owner --no-privileges --exit-on-error /backup.dump
docker exec teste-backup psql -U postgres -d restaurado -c 'SELECT count(*) FROM pacientes_paciente'
docker rm -f teste-backup
```

With `--exit-on-error`, any problem in the file fails the test. The repository has a script that does all of this for the Google Cloud bucket: `deploy/testar_backup.sh`.

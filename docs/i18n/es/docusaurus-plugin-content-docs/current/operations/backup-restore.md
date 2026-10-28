---
sidebar_position: 2
title: Backup y restauración
---

# Backup y restauración

Todo el sistema está en la base PostgreSQL: pacientes, agenda, finanzas, usuarios y la auditoría. Un backup es un `pg_dump` de ella. **Un backup solo vale si se puede restaurar**: pruébelo de vez en cuando.

## Instalación en Google Cloud

Ya viene listo: todos los días a las 06:00 UTC el dump va al bucket de Cloud Storage, y cada archivo se borra a los 30 días. Si falla, se reintenta cada 20 minutos (hasta 4 veces en 3 horas). Cada backup exitoso se registra en el sistema; cuando el último tiene más de 26 horas, los superusuarios ven un aviso arriba de las pantallas.

```bash
sudo /opt/kaladrius/bin/backup.sh                       # en la VM: backup ahora
gcloud storage ls -l gs://<bucket>/                         # en su computadora: listar
```

## Servidor propio

Cree `/opt/kaladrius/backup.sh`:

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

Prográmelo todos los días a las 3 de la mañana:

```bash
sudo chmod 700 /opt/kaladrius/backup.sh
echo '0 3 * * * root /opt/kaladrius/backup.sh >> /var/log/kaladrius-backup.log 2>&1' | sudo tee /etc/cron.d/kaladrius-backup
```

- `registrar_backup` registra el backup, para que funcione el aviso a los superusuarios.
- `aplicar_retencao` borra los intentos de ingreso rechazados con más de 30 días (política de privacidad).

:::warning
Un backup en el mismo disco no sobrevive a la pérdida del servidor. Copie `/var/backups/kaladrius` todos los días a otro lugar: otro servidor, un almacenamiento de objetos (S3, Backblaze B2, Google Cloud Storage) con `rclone`, o un disco externo cifrado. Los archivos contienen datos de pacientes: manténgalos privados y cifrados.
:::

## Restaurar

:::danger
Restaurar **reemplaza** la base actual por el backup. Todo lo registrado después del backup se pierde.
:::

```bash
# Servidor propio
kaladrius exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < /var/backups/kaladrius/<archivo>.dump
kaladrius restart app

# Google Cloud, en la VM
gcloud storage cp gs://<bucket>/<archivo>.dump /tmp/restaurar.dump
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restaurar.dump
```

## Probar un backup sin tocar el servidor

Restáurelo en un PostgreSQL descartable, en cualquier computadora con Docker, y vea qué contiene:

```bash
docker run -d --rm --name teste-backup -e POSTGRES_PASSWORD=teste postgres:16-alpine
sleep 5
docker exec teste-backup createdb -U postgres restaurado
docker cp <archivo>.dump teste-backup:/backup.dump
docker exec teste-backup pg_restore -U postgres -d restaurado --no-owner --no-privileges --exit-on-error /backup.dump
docker exec teste-backup psql -U postgres -d restaurado -c 'SELECT count(*) FROM pacientes_paciente'
docker rm -f teste-backup
```

Con `--exit-on-error`, cualquier problema en el archivo hace fallar la prueba. El repositorio tiene un script que hace todo esto con el bucket de Google Cloud: `deploy/testar_backup.sh`.

---
sidebar_position: 2
title: Backup e restauração
---

# Backup e restauração

O sistema inteiro está no banco PostgreSQL: pacientes, agenda, financeiro, usuários e a auditoria. Um backup é um `pg_dump` dele. **Backup só vale se voltar**: teste de tempos em tempos.

## Instalação no Google Cloud

Já vem pronto: todo dia às 06:00 UTC o dump vai para o bucket do Cloud Storage, e cada arquivo é apagado depois de 30 dias. Se falhar, tenta de novo a cada 20 minutos (até 4 vezes em 3 horas). Cada backup bem-sucedido é registrado no sistema; quando o último tem mais de 26 horas, os superusuários veem um aviso no topo das telas.

```bash
sudo /opt/medical-system/bin/backup.sh                       # na VM: backup agora
gcloud storage ls -l gs://<bucket>/                         # no seu computador: listar
```

## Servidor próprio

Crie `/opt/kaladrius/backup.sh`:

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

Agende para todo dia às 3 da manhã:

```bash
sudo chmod 700 /opt/kaladrius/backup.sh
echo '0 3 * * * root /opt/kaladrius/backup.sh >> /var/log/kaladrius-backup.log 2>&1' | sudo tee /etc/cron.d/kaladrius-backup
```

- `registrar_backup` registra o backup, para o aviso aos superusuários funcionar.
- `aplicar_retencao` apaga as tentativas de entrada recusadas com mais de 30 dias (política de privacidade).

:::warning
Um backup no mesmo disco não sobrevive à perda do servidor. Copie `/var/backups/kaladrius` todo dia para outro lugar: outro servidor, um armazenamento de objetos (S3, Backblaze B2, Google Cloud Storage) com o `rclone`, ou um disco externo criptografado. Os arquivos têm dados de pacientes: mantenha-os privados e criptografados.
:::

## Restaurar

:::danger
Restaurar **substitui** o banco atual pelo backup. Tudo o que foi registrado depois do backup se perde.
:::

```bash
# Servidor próprio
kaladrius exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < /var/backups/kaladrius/<arquivo>.dump
kaladrius restart app

# Google Cloud, na VM
gcloud storage cp gs://<bucket>/<arquivo>.dump /tmp/restaurar.dump
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restaurar.dump
```

## Testar um backup sem tocar no servidor

Restaure num PostgreSQL descartável, em qualquer computador com Docker, e veja o que tem dentro:

```bash
docker run -d --rm --name teste-backup -e POSTGRES_PASSWORD=teste postgres:16-alpine
sleep 5
docker exec teste-backup createdb -U postgres restaurado
docker cp <arquivo>.dump teste-backup:/backup.dump
docker exec teste-backup pg_restore -U postgres -d restaurado --no-owner --no-privileges --exit-on-error /backup.dump
docker exec teste-backup psql -U postgres -d restaurado -c 'SELECT count(*) FROM pacientes_paciente'
docker rm -f teste-backup
```

Com `--exit-on-error`, qualquer problema no arquivo faz o teste falhar. O repositório tem um script que faz tudo isso com o bucket do Google Cloud: `deploy/testar_backup.sh`.

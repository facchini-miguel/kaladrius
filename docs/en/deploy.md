# Deploy (Google Cloud, free tier)

🇺🇸 English | [🇧🇷 Português](../pt-BR/deploy.md) | [🇪🇸 Español](../es/despliegue.md)

Published at **https://medical-system.duckdns.org** (**IPv6-only** access). Fallback address: https://2600-1900-4020-f0b-0-0-0-0.sslip.io.

- **DNS:** `medical-system.duckdns.org` (DuckDNS, free) has only an AAAA record for the VM's IPv6. The token is in `DUCKDNS_TOKEN` in the server `.env` and the local `.env.producao`. To repoint: `https://www.duckdns.org/update?domains=medical-system&token=<token>&ipv6=<ipv6>` (when `ipv6` is given, DuckDNS does not fill in IPv4).
- **Static IPv6:** reserved address `medical-system-ipv6` (`2600:1900:4020:f0b::`), free; it does not change when the VM restarts.

## Architecture

```
git push (main) ─> GitHub Actions: tests ─> build ─> Artifact Registry (us-east1)
                                                        │ the VM checks every 5 min
                                                        ▼
Browser ──IPv6/HTTPS──> e2-micro VM "medical-system" (us-east1-b, no public IPv4)
                         ├─ caddy  (automatic Let's Encrypt HTTPS, host network)
                         ├─ app    (Django + Gunicorn, only on 127.0.0.1:8000)
                         ├─ db     (PostgreSQL 16, pgdata volume)
                         └─ daily backup 06:00 UTC ─> gs://medical-system-facchini-backups
Maintenance: SSH only through Google's IAP tunnel
```

## Why IPv6
Google charges for public IPv4 on VMs (US$ 0.005/hour, about US$ 3.65/month; the free tier covers only 1 hour/month). External IPv6 is free. As a result, the system only opens on IPv6-capable networks (most mobile and many fixed networks in Brazil). To serve any network, add an IPv4 to the VM (cost above). See the [pricing page](https://cloud.google.com/vpc/network-pricing).

## Resources (project `medical-system-facchini`)

| Resource | Name | Cost |
|---|---|---|
| VM | `medical-system` (e2-micro, us-east1-b, 30 GB standard disk, Debian 13) | Free tier |
| Network | VPC `medical-system`, subnet `medical-system-us-east1` (internal IPv4 + external IPv6, Private Google Access) | Free |
| Static IPv6 | `medical-system-ipv6` (`2600:1900:4020:f0b::`, reserved) | Free |
| Domain | `medical-system.duckdns.org` (DuckDNS) | Free |
| Firewall | `medical-system-web-ipv6` (TCP 80/443 and UDP 443 for HTTP/3, from ::/0), `medical-system-icmpv6`, `medical-system-ssh-iap` (22 from IAP only) | Free |
| Images | Artifact Registry `medical-system` (us-east1), automatic cleanup (keeps 5 versions) | Free tier (0.5 GB) |
| Backups | `gs://medical-system-facchini-backups` (us-east1, private, deleted after 30 days) | Free tier (5 GB) |
| Service accounts | `medical-system-vm` (reads images, writes backups), `github-ci` (publishes images) | Free |
| GitHub → Google | Workload Identity Federation (pool `github`), this repository and `main` only | Free |
| Budget alert | R$ 5 (notifications at 10%, 50% and 100%) | Free |

## How the server works
- `deploy/servidor/instalar.sh` is the VM startup script: installs Docker, adds 1 GB of swap, installs the systemd timers and starts the stack. Safe to run again.
- `deploy/servidor/atualizar.sh` (every 5 min): pulls the `latest` image; if it differs from the last one installed successfully (`/opt/medical-system/imagem-instalada`), extracts the `deploy/` files from the image, updates the systemd units and restarts the containers. If anything fails, the next run tries again. Migrations run when the app starts.
- `deploy/servidor/backup.sh` (daily): `pg_dump` uploaded to Cloud Storage and recorded in the system; then deletes refused login attempts older than 30 days (`aplicar_retencao`). If it fails, systemd retries every 20 minutes (up to 4 attempts in 3 hours). If the newest recorded backup is older than 26 hours, superusers see a warning at the top of every screen.
- The production compose file reads its `${...}` variables from `.env`, linked next to it (`/opt/medical-system/release/.env` → `../.env`). Only the app receives the whole file.
- Settings and passwords: `/opt/medical-system/.env` (root only). Local copy in `.env.producao`, ignored by Git.
- No stored keys: the VM and CI use short-lived Google tokens.

## Common tasks

```bash
# Log into the server (IAP tunnel)
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap

# On the VM: status, logs and Django commands
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <command>

# Update now / back up now
sudo /opt/medical-system/bin/atualizar.sh --forcar
sudo /opt/medical-system/bin/backup.sh

# List backups (on your machine)
gcloud storage ls -l gs://medical-system-facchini-backups/
```

### Rolling back to a previous version
The normal way is to revert the commit (`git revert`) and push to `main`: CI publishes a new image and the VM installs it within 5 minutes. In an emergency, an old image can be pinned on the VM (each version has an `X.Y.Z` tag that never moves, and each commit a tag with the first 12 characters of its SHA):

```bash
sudo systemctl stop medical-system-atualizar.timer   # otherwise the VM goes back to latest in 5 min
cd /opt/medical-system/release
sudo IMAGEM_APP=us-east1-docker.pkg.dev/medical-system-facchini/medical-system/app:0.7.0 \
  docker compose -f docker-compose.prod.yml up -d app
# After fixing and publishing: sudo systemctl start medical-system-atualizar.timer
```
Migrations are not undone: an old version only works if the new migrations are compatible with it (only adding tables and fields, for example).

### Importing the legacy system data
Confirmed by the owner on 2026-10-27, into the clinic "Clínica Sorriso" (LGPD: the data is stored in the US, and backups will then hold real data too). See [legacy-system.md](legacy-system.md).

```bash
# 1. Delete the fake data ("(teste)" clinics, their data and the test users)
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py remover_dados_teste --confirmar'

# 2. On your machine: the dump goes through the IAP tunnel straight into the command, never stored on the VM
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py importar_legado - --clinica "Clínica Sorriso"' \
  < ~/medical-system-old_data/backup_20191106/facchini07_20191106.sql
```
Then link the clinic administrator in the Django admin (Memberships) and create the team in Records > Team. The superuser already reaches the clinic through the clinic switcher.

### Anonymizing the imported data
The Clínica Sorriso data is used only as test data (decision 047). To anonymize it (irreversible; see [legacy-system.md](legacy-system.md)):

```bash
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py anonimizar_clinica --clinica "Clínica Sorriso" --confirmar'
```
Running it before the first daily backup after the import (06:00 UTC) keeps the real data out of every backup.

To give the test clinic current appointments and recalls (see [legacy-system.md](legacy-system.md)):
```bash
gcloud compute ssh medical-system --zone=us-east1-b --tunnel-through-iap --command \
  'cd /opt/medical-system/release && sudo docker compose -f docker-compose.prod.yml exec -T app python manage.py simular_movimento --clinica "Clínica Sorriso" --confirmar'
```

### Restoring a backup
```bash
# On the VM (replaces the current database!)
gcloud storage cp gs://medical-system-facchini-backups/<file>.dump /tmp/restore.dump  # or download on your machine and copy with gcloud compute scp --tunnel-through-iap
cd /opt/medical-system/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restore.dump
```

### Testing a backup restore
A backup is only worth something if it comes back. The test runs on your machine, in a throwaway PostgreSQL: it downloads the backup, restores it (failing on any error), shows how many rows each table has and the latest migration, and deletes everything at the end. It does not touch the server or the development database.

```bash
deploy/testar_backup.sh                 # the newest backup
deploy/testar_backup.sh <file>.dump     # a specific one
```
Done on 2026-10-27 with the 10/26 backup (fake data of that time): restored without errors in 9 seconds. The same test showed that that day's automatic backup had failed (the server was between 0.7.0 and 0.8.0, without the `.env` link) and that the web warning did not show when **no** backup had ever been recorded; since 0.17.1 superusers see that case too (`DJANGO_BACKUP_MONITORADO`, on by default when `DJANGO_DEBUG` is off).

## Cautions
- **Real patient data:** data lives in the US (free tier requirement). Before real use, review the LGPD (international transfer, art. 33) or move to the São Paulo region (paid).
- The **standard** disk is the free one; the console suggests "balanced", which is billed.
- With real data on the server, **do not run** `popular_dados_teste` in production: it creates users that share one password (`DJANGO_SEED_PASSWORD`). To delete them, `remover_dados_teste --confirmar`, which never touches real clinics or users.

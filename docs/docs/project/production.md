---
sidebar_position: 4
---

# Reference production

Published at **https://kaladrius.facchini.eti.br** (**IPv6-only** access), also at https://kaladrius.duckdns.org. Fallback address: https://2600-1900-4020-f0b-0-0-0-0.sslip.io.

- **DNS:** `kaladrius.duckdns.org` (DuckDNS, free) has only an AAAA record for the VM's IPv6. The token is in `DUCKDNS_TOKEN` in the server `.env` and the local `.env.producao`. To repoint: `https://www.duckdns.org/update?domains=kaladrius&token=<token>&ipv6=<ipv6>` (when `ipv6` is given, DuckDNS does not fill in IPv4). Watch out: when a subdomain is **created** on the website, DuckDNS fills in the IPv4 of whoever created it (your home); clear it with `&clear=true` and point only the `ipv6` again.
- **Documentation:** the site in `docs/` runs on the same server, at https://kaladrius-docs.facchini.eti.br, also at https://docs.kaladrius.duckdns.org (DuckDNS answers any `*.kaladrius.duckdns.org` with the same IPv6, nothing to create). CI publishes the `docs` image next to `app`; it only starts with `COMPOSE_PROFILES=docs` and `DOCS_HOSTNAME` in the server `.env`. It is public and open to search engines since the code was opened (decision 077). To view it on your computer: `docker compose --profile docs up --build docs` → http://localhost:3000.
- **Owner's domain:** `kaladrius.facchini.eti.br` and `kaladrius-docs.facchini.eti.br` are CNAMEs at Registro.br to the DuckDNS names, so they follow the IPv6 with nothing to update. The server accepts every name: `SITE_HOSTNAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and `DOCS_HOSTNAME` are comma lists, and Caddy gets one certificate per name (decision 084).
- **Static IPv6:** reserved address `kaladrius-ipv6` (`2600:1900:4020:f0b::`), free; it does not change when the VM restarts.

## Architecture

```
git push (main) ─> GitHub Actions: tests ─> build ─> Artifact Registry (us-east1)
                                                        │ the VM checks every 5 min
                                                        ▼
Browser ──IPv6/HTTPS──> e2-micro VM "medical-system" (us-east1-b, no public IPv4)
                         ├─ caddy  (automatic Let's Encrypt HTTPS, host network)
                         ├─ app    (Django + Gunicorn, only on 127.0.0.1:8000)
                         ├─ db     (PostgreSQL 16, pgdata volume)
                         └─ daily backup 06:00 UTC ─> gs://kaladrius-backups
Maintenance: SSH only through Google's IAP tunnel
```

## Why IPv6
Google charges for public IPv4 on VMs (US$ 0.005/hour, about US$ 3.65/month; the free tier covers only 1 hour/month). External IPv6 is free. As a result, the system only opens on IPv6-capable networks (most mobile and many fixed networks in Brazil). To serve any network, add an IPv4 to the VM (cost above). See the [pricing page](https://cloud.google.com/vpc/network-pricing).

## Resources (project `medical-system-facchini`, display name "Kaladrius")

| Resource | Name | Cost |
|---|---|---|
| VM | `kaladrius` (e2-micro, us-east1-b, 30 GB standard disk, Debian 13) | Free tier |
| Network | VPC `medical-system`, subnet `medical-system-us-east1` (internal IPv4 + external IPv6, Private Google Access) | Free |
| Static IPv6 | `kaladrius-ipv6` (`2600:1900:4020:f0b::`, reserved) | Free |
| Domain | `kaladrius.facchini.eti.br` and `kaladrius-docs.facchini.eti.br` (owner's domain at Registro.br, CNAMEs to DuckDNS); `kaladrius.duckdns.org` (DuckDNS) | Free (DuckDNS); the owner pays for his domain |
| Firewall | `medical-system-web-ipv6` (TCP 80/443 and UDP 443 for HTTP/3, from ::/0), `medical-system-icmpv6`, `medical-system-ssh-iap` (22 from IAP only) | Free |
| Images | Artifact Registry `kaladrius` (us-east1), automatic cleanup (keeps 5 versions) | Free tier (0.5 GB) |
| Backups | `gs://kaladrius-backups` (us-east1, private, deleted after 30 days) | Free tier (5 GB) |
| Service accounts | `kaladrius-vm` (reads images, writes backups), `github-ci` (publishes images) | Free |
| GitHub → Google | Workload Identity Federation (pool `github`), this repository and `main` only | Free |
| Budget alert | R$ 5 (notifications at 10%, 50% and 100%) | Free |

## How the server works
- `deploy/servidor/instalar.sh` is the VM startup script: installs Docker, adds 1 GB of swap, installs the systemd timers and starts the stack. Safe to run again.
- `deploy/servidor/atualizar.sh` (every 5 min): pulls the `latest` image; if it differs from the last one installed successfully (`/opt/kaladrius/imagem-instalada`), extracts the `deploy/` files from the image, updates the systemd units and restarts the containers. If anything fails, the next run tries again. Migrations run when the app starts.
- `deploy/servidor/backup.sh` (daily): `pg_dump` uploaded to Cloud Storage and recorded in the system; then deletes refused login attempts older than 30 days (`aplicar_retencao`). If it fails, systemd retries every 20 minutes (up to 4 attempts in 3 hours). If the newest recorded backup is older than 26 hours, superusers see a warning at the top of every screen.
- `deploy/servidor/saude.sh --coletar` (every 5 min, since 0.22.0): reads processor, memory, swap, disk, network and load with Linux tools (`/proc`, `df`) and each container's memory and processor (`docker stats`), and appends a line to `/opt/kaladrius/saude/amostras.jsonl` (7 days kept, about 1.5 MB). The app reads that file, read-only, and shows **Administration > System health** to superusers, with a warning at the top of every screen if collection stops or memory, swap or disk reach the critical level. The app has no access to Docker. Without arguments, `saude.sh` prints a report in the terminal.
- The production compose file reads its `${...}` variables from `.env`, linked next to it (`/opt/kaladrius/release/.env` → `../.env`). Only the app receives the whole file.
- Settings and passwords: `/opt/kaladrius/.env` (root only). Local copy in `.env.producao`, ignored by Git.
- No stored keys: the VM and CI use short-lived Google tokens.

## Common tasks

```bash
# Log into the server (IAP tunnel)
gcloud compute ssh kaladrius --zone=us-east1-b --tunnel-through-iap

# On the VM: status, logs and Django commands
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <command>

# Update now / back up now
sudo /opt/kaladrius/bin/atualizar.sh --forcar
sudo /opt/kaladrius/bin/backup.sh

# Server health: now, last 24 hours, containers and timers
sudo /opt/kaladrius/bin/saude.sh

# List backups (on your machine)
gcloud storage ls -l gs://kaladrius-backups/
```

### Rolling back to a previous version
The normal way is to revert the commit (`git revert`) and push to `main`: CI publishes a new image and the VM installs it within 5 minutes. In an emergency, an old image can be pinned on the VM (each version has an `X.Y.Z` tag that never moves, and each commit a tag with the first 12 characters of its SHA):

```bash
sudo systemctl stop kaladrius-atualizar.timer   # otherwise the VM goes back to latest in 5 min
cd /opt/kaladrius/release
sudo IMAGEM_APP=us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/app:0.7.0 \
  docker compose -f docker-compose.prod.yml up -d app
# After fixing and publishing: sudo systemctl start kaladrius-atualizar.timer
```
Migrations are not undone: an old version only works if the new migrations are compatible with it (only adding tables and fields, for example).

### Restoring a backup
```bash
# On the VM (replaces the current database!)
gcloud storage cp gs://kaladrius-backups/<file>.dump /tmp/restore.dump  # or download on your machine and copy with gcloud compute scp --tunnel-through-iap
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /tmp/restore.dump
```

### Testing a backup restore
A backup is only worth something if it comes back. The test runs on your machine, in a throwaway PostgreSQL: it downloads the backup, restores it (failing on any error), shows how many rows each table has and the latest migration, and deletes everything at the end. It does not touch the server or the development database.

```bash
deploy/testar_backup.sh                 # the newest backup
deploy/testar_backup.sh <file>.dump     # a specific one
```
Done on 2026-10-27 with the 10/26 backup (fake data of that time): restored without errors in 9 seconds. The same test showed that that day's automatic backup had failed (the server was between 0.7.0 and 0.8.0, without the `.env` link) and that the web warning did not show when **no** backup had ever been recorded; since 0.17.1 superusers see that case too (`DJANGO_BACKUP_MONITORADO`, on by default when `DJANGO_DEBUG` is off).

## Public demo logins
The demo publishes one login per role on the owner's website: `demo.recepcao`, `demo.profissional`, `demo.financeiro` and `demo.admin` (decisions 085 and 089). As demo logins, they never change their password, upload attachments, change the team or the clinic settings, nor see IP addresses in the audit log. To create them, or to reset their passwords:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py contas_demonstracao \
  --clinica "Clínica Sorriso" --profissional "Dra. Demonstração" --criar-profissional \
  --senha-recepcao <published password> --senha-profissional <published password> \
  --senha-financeiro <published password> --senha-admin <published password>
```

Never use the `DJANGO_SEED_PASSWORD` password there: the seed users, the seed administrator included, share it.

### Nightly reset (decision 086)
Every day at 07:30 UTC (04:30 in Brasília, after the backup) the server restores a saved **base** of the demo, dropping what visitors changed, and moves every date forward by the whole weeks since the base was saved, so the schedule always looks current and each appointment keeps its weekday (birth dates do not move). The list of backups is kept. It only runs with `DJANGO_DEMONSTRACAO=1` in the server `.env`. To turn it on, once:

```bash
echo 'DJANGO_DEMONSTRACAO=1' | sudo tee -a /opt/kaladrius/.env
sudo /opt/kaladrius/bin/reiniciar_demonstracao.sh --salvar-base
```

The reset also brings back **the owner's** account and settings as they were in the base: after changing a password or a setting that should stay, save the base again (`--salvar-base`). To reset right away: `sudo systemctl start kaladrius-demonstracao.service`.

## Cautions
- **Real patient data:** data lives in the US (free tier requirement). Before real use, review the LGPD (international transfer, art. 33) or move to the São Paulo region (paid).
- The **standard** disk is the free one; the console suggests "balanced", which is billed.
- With real data on the server, **do not run** `popular_dados_teste` in production: it creates users that share one password (`DJANGO_SEED_PASSWORD`). To delete them, `remover_dados_teste --confirmar`, which never touches real clinics or users.

---
sidebar_position: 4
---

# Reference production

Published at **https://kaladrius.facchini.eti.br** (IPv4 and IPv6), also at https://kaladrius.duckdns.org. The documentation site is at **https://kaladrius-docs.facchini.eti.br**, also at https://docs.kaladrius.duckdns.org. Since 2026-11-09 both run on the owner's VPS, managed with [Dokploy](https://dokploy.com) (decision 208); before that, on a Google Cloud free-tier VM with IPv6 only.

- **DNS:** at Registro.br, `kaladrius` and `kaladrius-docs` have an `A` record (`179.66.139.4`) and an `AAAA` record (`2a02:4780:95:91b7::1`). Registro.br refuses a CNAME and an A/AAAA with the same name in one save: to turn a CNAME into A/AAAA, save the removal first, then the new records. `kaladrius.duckdns.org` points to the same two addresses (`https://www.duckdns.org/update?domains=kaladrius&token=<token>&ip=<ipv4>&ipv6=<ipv6>`; the token is `DUCKDNS_TOKEN` in the server `.env`), and DuckDNS answers any `*.kaladrius.duckdns.org` with them.
- **Names:** the server accepts every name. `SITE_HOSTNAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and `DOCS_HOSTNAME` are comma lists, and Traefik gets one certificate per name, each with its own router, so a name whose DNS is not ready does not hold back the others.
- **Documentation:** public and open to search engines since the code was opened (decisions 077 and 207). To view it on your computer: `docker compose --profile docs up --build docs` → http://localhost:3000.

## Architecture

```
git push (main) ─> GitHub Actions: tests, docs build ─> image on ghcr.io
                                                          │ the server checks every 5 min
                                                          ▼
Browser ──IPv4/IPv6, HTTPS──> VPS (Ubuntu 24.04, Hostinger, Boston, US)
                               ├─ traefik  (Dokploy's proxy: Let's Encrypt HTTPS, ports 80/443)
                               └─ Dokploy Compose "kaladrius"
                                   ├─ app   (Django + Gunicorn, image from ghcr.io)
                                   ├─ db    (PostgreSQL 16, volume pgdata)
                                   └─ docs  (built from docs/ of main when deploying)
Daily backup 06:00 UTC ─> /var/backups/kaladrius (30 days)
Maintenance: SSH with a key only (no password, no root); Dokploy's panel only through an SSH tunnel
```

## Server

| Item | Value |
|---|---|
| Machine | VPS at Hostinger (Boston, US): 8 vCPUs, 32 GB of RAM, 400 GB of disk, Ubuntu 24.04 |
| Access | `ssh facchini@179.66.139.4`, with a key only; `sudo` for administration |
| Firewall | ufw: only 22, 80 and 443. Docker publishes ports outside ufw, so Dokploy's panel (3000) is closed to the internet by a rule in the `DOCKER-USER` chain (`bloquear-painel-dokploy.service`) |
| Dokploy | project **Kaladrius**, Compose **kaladrius** (raw Compose file kept in Dokploy). The panel: `ssh -L 3000:localhost:3000 facchini@179.66.139.4`, then http://localhost:3000 |
| Settings | the Compose's environment in Dokploy (written as `.env` next to the Compose file). It comes from the Google Cloud `.env`, without the `sslip.io` name |

The Compose file follows `deploy/docker-compose.prod.yml`, with Traefik in Caddy's place: the labels give HTTPS for each name, redirect HTTP to HTTPS, compress the responses, drop the `Server` header and cap a request body at 11 MB (the largest legitimate upload is a 10 MB medical record attachment, like the Caddyfile's `request_body`). The app trusts the client address Traefik puts last in `X-Forwarded-For` (`DJANGO_REVERSE_PROXY=1`).

**The documentation does not depend on the app** (decision 209): its routers use their own Traefik middlewares (`kaladrius-docs-comprime`, `kaladrius-docs-sem-server`, `kaladrius-docs-https`), declared on the `docs` service. When they used the ones declared on `app`, Traefik dropped the documentation's routers whenever the app stopped (the nightly reset, every update). `update-dokploy.sh`, like `reset_demo.sh`, marks the stop as maintenance, so `health.sh` does not report it.

## How the server works

The scripts of `deploy/server/` run as they are, from `/opt/kaladrius/bin`, with the systemd units of the repository. `/opt/kaladrius` links them to the Dokploy Compose:

- `release/docker-compose.prod.yml` and `release/.env` are links to Dokploy's Compose file and `.env`. The `.env` names the Compose project (`COMPOSE_PROJECT_NAME`), so `docker compose -f /opt/kaladrius/release/docker-compose.prod.yml` reaches the containers Dokploy started.
- `/opt/kaladrius/.env` is a copy without quotes, which `sync-env.py` writes again before every `kaladrius-*` unit (drop-in `/etc/systemd/system/kaladrius-.service.d/env.conf`). Dokploy writes `KEY="value"`, which Docker Compose reads, but `env_value` in `common.sh` reads the line as it is: with quotes, `DJANGO_DEMO="1"` would never match `1` and the monitor addresses would be invalid. Change settings in Dokploy, never in this copy.
- `release/linux-package` puts the scripts in the mode of an installation on its own server (decision 140): backups and the restore test in a local folder, and the sites checked through the server itself. The image and the updates stay with Dokploy.

| Timer | What it does |
|---|---|
| `kaladrius-update.timer` (every 5 min) | `update-dokploy.sh`: pulls `ghcr.io/facchini-miguel/kaladrius:latest`; when it differs from the running app, asks Dokploy for a deploy of the Compose (new app, docs built again from main), waits for `/api/v1/health` and tells `MONITOR_UPDATE_URL`. Migrations run when the app starts. There is no automatic rollback (decision 135) here: see below |
| `kaladrius-backup.timer` (06:00 UTC) | `backup.sh`: `pg_dump` to `/var/backups/kaladrius`, keeping `KALADRIUS_BACKUP_DAYS` (30) days; records it in the system and applies the 30-day retention of refused logins |
| `kaladrius-restore-test.timer` (Sundays 07:00 UTC) | `test_restore.sh`: restores the newest backup into a throwaway database and checks it |
| `kaladrius-demo-reset.timer` (07:30 UTC) | `reset_demo.sh`: the nightly reset of the demo (below) |
| `kaladrius-health.timer` (every 5 min) | `health.sh --collect`: the samples of **Administration > System health** (`/opt/kaladrius/health`) and the monitors of the sites, certificates and resources |
| `backup-dokploy.timer` (05:30 UTC) | Dokploy's own database and `/etc/dokploy` to `/var/backups/dokploy` (14 days) |

The external monitors (Healthchecks.io, decision 078) are the `MONITOR_*_URL` of the `.env`, the same ones as on Google Cloud.

**Backups stay on the VPS disk for now.** A copy in another place is still to be chosen. The 18 backups of the Google Cloud bucket (10/26 to 11/09) are in `/var/backups/kaladrius/google`.

## Common tasks

```bash
# Log into the server
ssh facchini@179.66.139.4

# On the server: status, logs and Django commands
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs -f app
sudo docker compose -f docker-compose.prod.yml exec app python manage.py <command>

# Update now / back up now
sudo systemctl start kaladrius-update.service
sudo systemctl start kaladrius-backup.service

# Server health: now, last 24 hours, containers and timers
sudo /opt/kaladrius/bin/health.sh

# List backups
sudo ls -l /var/backups/kaladrius
```

### Rolling back to a previous version
The normal way is to revert the commit (`git revert`) on a branch and merge it into `main` through a pull request (`main` takes nothing else, decision 141; the admin may push it straight, bypassing the ruleset): CI publishes a new image and the server installs it within 5 minutes of the merge. In an emergency, an old image can be pinned (each version has an `X.Y.Z` tag on ghcr.io that never moves, and each commit a tag with the first 12 characters of its SHA): stop `kaladrius-update.timer`, change the app's `image:` in the Compose file in Dokploy to `ghcr.io/facchini-miguel/kaladrius:<tag>` and deploy. After fixing and publishing, put `latest` back and start the timer again.

Migrations are not undone: an old version only works if the new migrations are compatible with it (adding tables, or fields that may be empty or have a `db_default`, for example; the migration report on each pull request flags the rest, decision 139).

### Restoring a backup
```bash
# On the server (replaces the current database!)
cd /opt/kaladrius/release
sudo docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /var/backups/kaladrius/<file>.dump
```

### Testing a backup restore
A backup is only worth something if it comes back. The server tests the newest one every Sunday (`kaladrius-restore-test.timer`), in a throwaway database that never touches the real one; to test now, `sudo systemctl start kaladrius-restore-test.service`. (`deploy/test_backup.sh` tests on your machine the backups of a Google Cloud bucket, the way of an installation on Google Cloud.)

Done on 2026-11-09, when moving to the VPS: the production dump restored without errors (9 users, 1,093 patients, 19,446 appointments), and the restore test passed with the first VPS backup.

## Public demo logins
The demo publishes one login per role on the owner's website: `demo.recepcao`, `demo.profissional`, `demo.financeiro` and `demo.admin` (decisions 085 and 089). As demo logins, they never change their password, upload attachments, change the team or the clinic settings, nor see IP addresses in the audit log. To create them, or to reset their passwords:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py demo_accounts \
  --clinic "Clínica Sorriso" --practitioner "Dra. Demonstração" --create-practitioner \
  --front-desk-password <published password> --practitioner-password <published password> \
  --finance-password <published password> --admin-password <published password>
```

Never use the `DJANGO_SEED_PASSWORD` password there: the seed users, the seed administrator included, share it.

### Nightly reset (decision 086)
Every day at 07:30 UTC (04:30 in Brasília, after the backup) the server restores a saved **base** of the demo, dropping what visitors changed, and moves every date forward by the whole weeks since the base was saved, so the schedule always looks current and each appointment keeps its weekday (birth dates do not move). The list of backups is kept. It only runs with `DJANGO_DEMO=1` in the server `.env` (in Dokploy). The base is `/opt/kaladrius/demo/base.dump`, brought from Google Cloud (saved on 2026-11-07) and saved again on the VPS on 2026-11-11, right after a reset, so the reset no longer replays the migrations since 0.62 (decision 209). Its date (`base-date`) stays 2026-11-07, the date of the appointments in it: a base saved right after a reset still holds the dates of the base before it, since the reset moves them only after a whole week. To save it again:

```bash
sudo /opt/kaladrius/bin/reset_demo.sh --save-base
```

The **system administrators'** accounts (superusers) are kept across the reset (decision 118): password, e-mail, language, two-step verification and recovery codes stay as they were. The rest of **the owner's** settings (the clinic's, for example) go back to the base: after changing one that should stay, save the base again (`--save-base`). To reset right away: `sudo systemctl start kaladrius-demo-reset.service`.

## Cautions
- **Real patient data:** the server is in the United States. Before real use, review the LGPD (international transfer, art. 33) or move to a server in Brazil.
- With real data on the server, **do not run** `seed_sample_data` in production: it creates users that share one password (`DJANGO_SEED_PASSWORD`). To delete them, `remove_sample_data --confirm`, which never touches real clinics or users.
- Dokploy's API key (`~/.dokploy-api-key` of `facchini` on the server) is what lets `update-dokploy.sh` deploy: when it expires or is revoked, the updates stop and `MONITOR_UPDATE_URL` reports it.

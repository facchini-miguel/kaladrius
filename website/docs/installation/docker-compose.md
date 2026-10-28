---
sidebar_position: 2
title: Own server (Docker Compose)
---

# Own server (Docker Compose)

This guide installs Kaladrius on any Linux server with Docker: a VPS, a machine in the clinic or a cloud VM. It runs three containers:

| Container | What it does |
|---|---|
| `caddy` | Receives the visits on ports 80 and 443, gets the HTTPS certificate automatically and forwards to the app |
| `app` | Kaladrius (Django + Gunicorn), reachable only from the server itself (`127.0.0.1:8000`) |
| `db` | PostgreSQL 16, with the data in a Docker volume |

Check the [requirements](requirements.md) first: the domain must already point to the server, and ports 80 and 443 must be open.

## 1. Install Docker and Git

On Debian 13:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git
sudo systemctl enable --now docker
```

On Ubuntu, the Compose plugin package is `docker-compose-v2` instead of `docker-compose`. Check with `docker compose version`.

For other distributions, see the [Docker documentation](https://docs.docker.com/engine/install/).

## 2. Get the code

```bash
sudo git clone https://github.com/facchini-miguel/kaladrius.git /opt/kaladrius
cd /opt/kaladrius
```

## 3. Configure

```bash
sudo cp .env.example .env
sudo chmod 600 .env
sudo nano .env
```

Change these values (the full list is in [Configuration](../configuration.md)):

```ini
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<a long random value>
DJANGO_ALLOWED_HOSTS=clinic.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://clinic.example.com
DJANGO_SECURE=1
DJANGO_PROXY_REVERSO=1

POSTGRES_PASSWORD=<a strong password>

DJANGO_ADMIN_USERNAME=admin
DJANGO_ADMIN_PASSWORD=<a strong password>

# Used by Caddy for the HTTPS certificate
SITE_HOSTNAME=clinic.example.com
# The image built in step 4
IMAGEM_APP=kaladrius:latest
# Server health samples are collected only on the Google Cloud installation
DJANGO_SAUDE_MONITORADA=0
```

To generate random values: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.

:::tip
Keep `DJANGO_BACKUP_MONITORADO` on (the default): superusers see a warning at the top of every page when no backup was recorded in the last 26 hours. [Backup and restore](../operations/backup-restore.md) shows how to schedule backups that record themselves.
:::

## 4. Build the image

```bash
sudo docker build -t kaladrius:latest .
```

## 5. Start

The commands below use the production file `deploy/docker-compose.prod.yml` with your `.env`. To type less, create a shortcut:

```bash
alias kaladrius='sudo docker compose -p kaladrius --env-file /opt/kaladrius/.env -f /opt/kaladrius/deploy/docker-compose.prod.yml'
```

(Add the line to `~/.bashrc` to keep it.) Then:

```bash
kaladrius up -d
kaladrius ps
```

The app applies the database migrations every time it starts. Caddy asks Let's Encrypt for the certificate on the first visit; it can take a minute.

## 6. Create the administrator

```bash
kaladrius exec app python manage.py criar_admin
```

Open `https://clinic.example.com`, log in and follow [First steps](../first-steps.md) to create the clinic and the team.

## Useful commands

```bash
kaladrius ps                                   # state of the containers
kaladrius logs -f app                          # app log (Ctrl+C to leave)
kaladrius logs -f caddy                        # HTTPS and access problems
kaladrius exec app python manage.py <command>  # Django commands
kaladrius restart app                          # restart after changing .env
kaladrius down                                 # stop (the data stays)
```

Next: [Upgrade](../operations/upgrade.md) and [Backup and restore](../operations/backup-restore.md).

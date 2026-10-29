---
sidebar_position: 4
title: Configuration
---

# Configuration

Everything that changes between installations lives in the **`.env`** file, next to the code (own server) or at `/opt/kaladrius/.env` (Google Cloud). It holds passwords: keep it readable only by root (`chmod 600`) and never put it in Git.

After changing it, restart: `kaladrius up -d` (the containers whose settings changed are recreated).

## Django

| Variable | Default | What it does |
|---|---|---|
| `DJANGO_SECRET_KEY` | **required** | Signs sessions and tokens. A long random value; changing it logs everybody out |
| `DJANGO_DEBUG` | `0` | `1` shows error details. **Never `1` on a server** |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Domains the system answers to, separated by commas |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | The same domains with `https://`, separated by commas |
| `DJANGO_SECURE` | `0` | `1` turns on the HTTPS protections: redirect to HTTPS, secure cookies, HSTS for one year. Use `1` on a server |
| `DJANGO_PROXY_REVERSO` | `0` | `1` when behind Caddy (or another proxy): takes the visitor's IP from `X-Forwarded-For`, for the audit log and the login lockout |
| `DJANGO_DEMONSTRACAO` | off | Public demo server only: enables the nightly reset of the demo (decision 086). Never on a clinic's server |
| `DJANGO_BACKUP_MONITORADO` | on when `DJANGO_DEBUG=0` | Warns superusers when no backup was recorded in the last 26 hours |
| `DJANGO_SAUDE_MONITORADA` | on when `DJANGO_DEBUG=0` | Warns superusers when the server health samples stop or a resource is critical. Set `0` outside the Google Cloud installation |
| `DJANGO_SAUDE_DIR` | `/saude` | Folder, inside the container, with the health samples |
| `DJANGO_DOCS_URL` | `https://kaladrius-docs.facchini.eti.br` | This documentation site. The **Help** menu opens it in the user's language |

## Database

| Variable | Default | What it does |
|---|---|---|
| `POSTGRES_DB` | `kaladrius` | Database name |
| `POSTGRES_USER` | `kaladrius` | Database user |
| `POSTGRES_PASSWORD` | empty | Database password. Use a strong one |
| `POSTGRES_HOST` | `localhost` | `db` with Docker Compose |
| `POSTGRES_PORT` | `5432` | |

The database container creates the database and the user from these values the first time it starts. Changing them later does not change an existing database.

## First administrator

Used only by `python manage.py criar_admin`, which does nothing if the user already exists.

| Variable | Default | What it does |
|---|---|---|
| `DJANGO_ADMIN_USERNAME` | `admin` | User name of the superuser |
| `DJANGO_ADMIN_PASSWORD` | **required by the command** | Password of the superuser |
| `DJANGO_ADMIN_EMAIL` | empty | E-mail of the superuser |

After the first login you can remove `DJANGO_ADMIN_PASSWORD` from the file.

## Production stack

| Variable | Default | What it does |
|---|---|---|
| `SITE_HOSTNAME` | **required** | Domain(s) Caddy serves and gets the HTTPS certificate for, separated by commas, e.g. `clinic.example.com, www.clinic.example.com` |
| `IMAGEM_APP` | the reference installation's registry | Docker image of the app, e.g. `kaladrius:latest` when you build it yourself |

## Development only

| Variable | What it does |
|---|---|
| `DJANGO_SEED_PASSWORD` | Password of the fake users created by `popular_dados_teste`. **Never** run that command on a server with real data: every fake user shares this password |

## Fixed settings

These are in `config/settings.py` and apply to every installation:

- **Time zone** `America/Sao_Paulo` and **default language** Portuguese (each user can switch to English or Spanish).
- **Sessions** last up to 8 hours and end when the browser closes.
- **Login lockout:** 5 wrong passwords for the same user from the same address block it for 1 hour.
- **Uploads** up to 6 MB (the largest is an OFX bank statement), limited by Caddy.

---
sidebar_position: 2
---

# Architecture notes

## Overview

```
                          ┌── Web (Django templates + HTMX) ─── clinic staff
Django + PostgreSQL ──────┤
(single back end)         └── API /api/v1 (Django Ninja) ───┬── App: practitioner/staff profile
                                                            └── App: patient profile
                                                                 + push (Firebase Cloud Messaging)
```

## Repositories (private)

| Repository | Contents | Phase |
|---|---|---|
| `kaladrius` (this one) | Django, staff web app, API, Docker, documentation | 1 |
| `kaladrius-app` | React Native + Expo (Android and iOS) | 2 |

The two communicate **only through the API**.

## Server stack

| Item | Choice | License |
|---|---|---|
| Language | Python 3.14 | PSF |
| Framework | Django (current stable; move to 6.2 LTS in Apr/2027) | BSD |
| API | Django Ninja | MIT |
| Database | PostgreSQL 16 | PostgreSQL (permissive) |
| Web interactivity | HTMX | BSD |
| Schedule calendar | FullCalendar (free plugins only) | MIT |
| Styling | Bootstrap 5 | MIT |
| Languages | Django translation (gettext); files compiled with GNU gettext, as a build tool only | BSD (Django); GPL (tool, not a code dependency) |
| Documents in the system | Python-Markdown | BSD |
| Application server | Gunicorn | MIT |
| Static files | WhiteNoise | MIT |
| Login attempt limiting | django-axes | MIT |
| HTTPS / proxy | Caddy | Apache 2.0 |
| Tests | pytest + pytest-django | MIT |
| Lint and formatting | Ruff | MIT |
| Dependency locks | pip-tools (`pip-compile`, every package pinned and hashed, decision 136), as a build tool only | BSD |

Rule: **no GPL/AGPL dependencies**, to keep the project's license choice open.

## Languages (version 0.13.0, decision 049)
- The interface exists in **Portuguese** (the default), **English** and **Spanish**. The texts are written in English in the code (the source, decision 200); the translations live in `locale/pt_BR/` and `locale/es/` (`django.po`); compiled files (`.mo`) are not in Git: they are built in the image and in CI.
- Each user chooses the language in the flag menu of the top bar (between the clinic and the user name; 0.13.1); the choice is stored in the profile (`Usuario.idioma`) and in a cookie (for the login page). Without a choice, the browser's language is used.
- Dates use the language's formats (`SHORT_DATE_FORMAT`); the schedule uses the matching FullCalendar locale; What's new has each text in the three languages.
- Kept in Portuguese: data (appointment type names, descriptions, cities), the audit log and the messages of terminal commands.
- CI fails if a new text was not extracted (`makemessages`) and a test fails if a translation is missing.

## Help (version 0.14.0, decision 050)
- **Help** menu with the **user manual** (`docs/<language>/manual/`, for the whole team, in the user's language), **What's new** and, for superusers only, the **technical documentation** (the rest of `docs/`, which describes the infrastructure).
- Markdown files become HTML on the server (`apps/help`). Links between documents become links inside the system; other repository files point to GitHub. Only `.md` files inside `docs/` are opened.

## Runtime (Docker Compose)

| Service | Local (`docker-compose.yml`) | Production (`deploy/docker-compose.prod.yml`) |
|---|---|---|
| `db` | postgres:16-alpine, persistent volume, no exposed port | Same, with memory tuned for the e2-micro |
| `app` | Image built on the machine, code mounted as a volume, Django's development server (reloads on save) | Artifact Registry image with Gunicorn, reachable only on `127.0.0.1:8000` |
| `caddy` | — | caddy:2-alpine on the host network: automatic HTTPS (Let's Encrypt) and proxy to the app |

In production only the app receives the whole `.env`; the database gets just the Postgres variables and Caddy just the site name. The project names differ (`medical-system-dev` locally, `medical-system` on the VM), so the two never share containers or volumes on the same machine. In both cases the app runs the migrations on startup and reads its configuration from `.env`. Backup is not a Compose service: a systemd timer on the VM runs `deploy/server/backup.sh` daily (`pg_dump` → Cloud Storage). Details in [deploy.md](production.md).

## Infrastructure

The reference production runs on the owner's VPS since 2026-11-09 (decision 208). Until then the rule was **Google Cloud free tier resources only** (decision 020), which made the server IPv6-only (decision 035).

| Environment | Where | Cost |
|---|---|---|
| Local | Docker on the developer's machine | — |
| Production (reference) | VPS at Hostinger (Boston, US), Ubuntu 24.04, IPv4 and IPv6, managed with Dokploy. Details in [Reference production](production.md) | Paid VPS |
| Backup | Local folder on the VPS (30 days); a copy elsewhere is still to be chosen | — |

**CI/CD:** GitHub Actions runs lint and tests and publishes the image to **GitHub Packages** (`ghcr.io`). The server checks every 5 minutes and asks Dokploy to deploy a new image; CI never reaches the server.

Anyone can still install Kaladrius on the Google Cloud free tier: see [Google Cloud free tier](../installation/google-cloud.md).

## Security (requirements)
- Django's built-in protections enabled (CSRF, XSS escaping, parameterized ORM, security headers). `manage.py check --deploy` with no warnings.
- Argon2 password hashing and login attempt limiting (django-axes: 5 failures per user + IP lock for 1 hour). For IPv6 the /48 network counts, not the address, since switching addresses inside one's own network is trivial (decision 041).
- No password recovery by e-mail (the server sends no e-mail): each person changes their own password in the menu with their name, and the clinic administrator sets a new one in Records > Team (decision 042).
- Audit log of changes, patient record views and logins (`apps/audit`).
- Behind Caddy, the real client IP comes from `X-Forwarded-For` (`DJANGO_REVERSE_PROXY=1`), used by django-axes and the audit log.
- **Per-clinic isolation** in every query, with automated tests that try to access another clinic's data.
- Secrets only in `.env` (outside Git) and in GitHub *Secrets*. Push protection enabled.
- Postgres port not exposed. VM firewall: only TCP 80/443 and UDP 443 (HTTP/3) from the internet; SSH only through Google's IAP tunnel.
- LGPD (Brazilian data protection law): access and change logging (audit), backups in a private bucket, encrypted at rest by Google (no encryption of our own) and deleted after 30 days. If a backup fails the server retries; if the newest one is older than 26 hours, superusers see a warning in the web app (decision 043). Data is hosted in the US (free tier requirement). Before real use with patients, review international data transfer rules (LGPD, art. 33) or move to a Brazilian region.

# Architecture

🇺🇸 English | [🇧🇷 Português](../pt-BR/arquitetura.md)

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
| `medical-system` (this one) | Django, staff web app, API, Docker, documentation | 1 |
| `medical-system-app` | React Native + Expo (Android and iOS) | 2 |

The two communicate **only through the API**.

## Server stack

| Item | Choice | License |
|---|---|---|
| Language | Python 3.13 | PSF |
| Framework | Django (current stable; move to 6.2 LTS in Apr/2027) | BSD |
| API | Django Ninja | MIT |
| Database | PostgreSQL 16 | PostgreSQL (permissive) |
| Web interactivity | HTMX | BSD |
| Schedule calendar | FullCalendar (free plugins only) | MIT |
| Styling | Bootstrap 5 | MIT |
| Application server | Gunicorn | MIT |
| HTTPS / proxy | Caddy | Apache 2.0 |
| Tests | pytest + pytest-django | MIT |
| Lint and formatting | Ruff | MIT |

Rule: **no GPL/AGPL dependencies**, to keep the project's license choice open.

## Runtime (Docker Compose)

| Service | Image | Role |
|---|---|---|
| `db` | postgres:16-alpine | Database, with a persistent volume |
| `app` | project image | Django + Gunicorn |
| `caddy` | caddy:2-alpine | Automatic HTTPS (production only) |
| `backup` | (deploy phase) | Daily encrypted pg_dump → Cloud Storage |

The same `docker-compose.yml` serves the local environment and the VM; only `.env` differs.

## Infrastructure

| Environment | Where | Cost |
|---|---|---|
| Local | Docker on the developer's machine | — |
| Testing | e2-micro VM (free tier, US) | Free |
| Production | e2-small VM, São Paulo region (`southamerica-east1`) | ~US$ 13–15/month |

**CI/CD:** GitHub Actions runs lint and tests, builds the image into GitHub Container Registry and deploys to the VM over SSH (`docker compose pull && up -d`).

## Security (requirements)
- Django's built-in protections enabled (CSRF, XSS escaping, parameterized ORM, security headers). `manage.py check --deploy` with no warnings.
- Argon2 password hashing and login attempt limiting.
- **Per-clinic isolation** in every query, with automated tests that try to access another clinic's data.
- Secrets only in `.env` (outside Git) and in GitHub *Secrets*. Push protection enabled.
- Postgres port not exposed. VM firewall (80, 443, key-only SSH).
- LGPD (Brazilian data protection law): access and change logging (audit), data hosted in Brazil in production, encrypted backups.

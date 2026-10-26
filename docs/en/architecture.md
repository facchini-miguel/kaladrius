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
| `backup` | (deploy phase) | Daily encrypted pg_dump → Cloud Storage (US bucket, free tier) |

The same `docker-compose.yml` serves the local environment and the VM; only `.env` differs.

## Infrastructure

Rule: **Google Cloud free tier resources only** (decision 020).

| Environment | Where | Cost |
|---|---|---|
| Local | Docker on the developer's machine | — |
| Cloud (testing and production) | **e2-micro** VM in `us-east1-b`, 30 GB standard disk, **public IPv6 only** (IPv4 is billed). Details in [deploy.md](deploy.md) | Free |
| Backup | Cloud Storage, US regional bucket, up to 5 GB | Free |

**Google Cloud project:** `medical-system-facchini`, with the Compute Engine API enabled and a **R$ 5 budget alert** (notifications at R$ 0.50, R$ 2.50 and R$ 5) to catch any charge.

**Free tier limits to respect:** 1 e2-micro VM, 30 GB standard disk, 5 GB in Cloud Storage, 1 GB/month egress. Disk snapshots are paid, so they are not used. The cost of the VM's external IP must be confirmed on the first billing report.

**CI/CD:** GitHub Actions runs lint and tests and publishes the image to Google **Artifact Registry** (keyless auth). The VM checks every 5 minutes and updates itself (GitHub has no IPv6, so the VM could not reach GHCR, nor could CI reach the VM over SSH).

## Security (requirements)
- Django's built-in protections enabled (CSRF, XSS escaping, parameterized ORM, security headers). `manage.py check --deploy` with no warnings.
- Argon2 password hashing and login attempt limiting (django-axes: 5 failures per user + IP lock for 1 hour).
- Audit log of changes, patient record views and logins (`apps/auditoria`).
- Behind Caddy, the real client IP comes from `X-Forwarded-For` (`DJANGO_PROXY_REVERSO=1`), used by django-axes and the audit log.
- **Per-clinic isolation** in every query, with automated tests that try to access another clinic's data.
- Secrets only in `.env` (outside Git) and in GitHub *Secrets*. Push protection enabled.
- Postgres port not exposed. VM firewall (80, 443, key-only SSH).
- LGPD (Brazilian data protection law): access and change logging (audit), encrypted backups. Data is hosted in the US (free tier requirement). Before real use with patients, review international data transfer rules (LGPD, art. 33) or move to a Brazilian region.

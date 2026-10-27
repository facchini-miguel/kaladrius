# Medical System

🇺🇸 English | [🇧🇷 Português](README.pt-BR.md)

Clinic management system: per-professional scheduling, patient records, recalls (follow-up reminders), birthdays, users and permissions. Serves multiple clinics from the same server (multi-tenant).

It is the rewrite of the old *Odonto System* (PHP 5, 2009–2019), now generic for any kind of clinic.

[![CI](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml)

**Current version: 0.9.0** · [What's new](releases.yaml) · [All releases](https://github.com/facchini-miguel/medical-system/releases)

> Status: **phase 1 complete** (feature parity with the legacy system), running at https://medical-system.duckdns.org (Google Cloud free tier, IPv6 only). See [docs/en/deploy.md](docs/en/deploy.md).

## Running locally

Requirement: Docker with Docker Compose v2 (the `docker compose` command).

```bash
cp .env.example .env          # fill in the passwords and SECRET_KEY (random values)
docker compose up --build -d  # starts the database and the application
docker compose exec app python manage.py criar_admin   # creates the admin defined in .env
```

Open http://localhost:8000. The API documentation is at http://localhost:8000/api/v1/docs.

| Task | Command |
|---|---|
| Test data (fake clinics, users, practitioners, 600 patients per clinic, 6 weeks of appointments and recalls) | `docker compose exec app python manage.py popular_dados_teste` |
| Delete the test data (never touches real clinics or users) | `docker compose exec app python manage.py remover_dados_teste --confirmar` |
| Import the legacy Odonto System data into a new clinic (see [docs/en/legacy-system.md](docs/en/legacy-system.md)) | `docker compose exec -T app python manage.py importar_legado - --clinica "Name" < dump.sql` |
| Tests (with coverage, minimum 90%) | `docker compose exec app pytest --cov` |
| Lint | `docker compose exec app ruff check .` |
| Format code | `docker compose exec app ruff format .` |
| New migration | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Stop | `docker compose down` (database data stays in the `medical-system-dev_pgdata` volume) |

## Stack

| Layer | Tool |
|---|---|
| Server and staff web app | Python + Django |
| API (for the mobile app) | Django Ninja |
| Database | PostgreSQL 16 |
| Runtime | Docker + Docker Compose |
| Production | Google Compute Engine VM |
| Mobile app | React Native + Expo, in the separate `medical-system-app` repository |

## Documentation

All documentation lives in [`docs/`](docs/README.md), in English ([`docs/en`](docs/en/README.md)) and Portuguese ([`docs/pt-BR`](docs/pt-BR/README.md)). Portuguese is the primary language; English is a translation.

## Versions

The version history lives in [`releases.yaml`](releases.yaml) and can also be viewed inside the system and in the app. See [docs/en/versioning-and-releases.md](docs/en/versioning-and-releases.md).

## License

Proprietary software. All rights reserved. See [LICENSE](LICENSE).

Developed by **Miguel Facchini**.

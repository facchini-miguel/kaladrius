<img src="static/img/logo.svg" alt="" width="72">

# Kaladrius

🇺🇸 English | [🇧🇷 Português](README.pt-BR.md) | [🇪🇸 Español](README.es.md)

Clinic management system: per-professional scheduling, patient records, recalls (follow-up reminders), birthdays, users and permissions. One installation serves one clinic.

It is the rewrite of the old *Odonto System* (PHP 5, 2009–2019), now generic for any kind of clinic.

[![CI](https://github.com/facchini-miguel/kaladrius/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/kaladrius/actions/workflows/ci.yml)

**Current version: 0.31.0** · [What's new](releases.yaml) · [All releases](https://github.com/facchini-miguel/kaladrius/releases)

> Status: **phase 1 complete** (feature parity with the legacy system), running at https://kaladrius.facchini.eti.br (Google Cloud free tier, IPv6 only). See [Reference production](https://kaladrius-docs.facchini.eti.br/project/production).

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
| Test data (a fake clinic, users, practitioners, 600 patients, 6 weeks of appointments and recalls) | `docker compose exec app python manage.py popular_dados_teste` |
| Compile the translations (after `git pull` or changing texts; the image does it at build time) | `docker compose exec app python manage.py compilemessages` |
| Extract new texts for translation (`locale/*/LC_MESSAGES/django.po`) | `docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests` |
| Delete the test data (never touches real clinics or users) | `docker compose exec app python manage.py remover_dados_teste --confirmar` |
| Import the legacy Odonto System data into a new clinic | `docker compose exec -T app python manage.py importar_legado - --clinica "Name" < dump.sql` |
| Anonymize a clinic's data to use it for testing (irreversible) | `docker compose exec app python manage.py anonimizar_clinica --clinica "Name" --confirmar` |
| Simulate current appointments and recalls in a **test** clinic | `docker compose exec app python manage.py simular_movimento --clinica "Name" --confirmar` |
| GitHub *Release* title and text (in English) | `docker compose exec app python manage.py notas_release X.Y.Z [--titulo]` |
| Test restoring a backup (downloads it and restores into a throwaway PostgreSQL) | `deploy/testar_backup.sh [file.dump]` |
| Tests (with coverage, minimum 90%) | `docker compose exec app pytest --cov` |
| Lint | `docker compose exec app ruff check .` |
| Format code | `docker compose exec app ruff format .` |
| New migration | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Stop | `docker compose down` (database data stays in the `kaladrius-dev_pgdata` volume) |

## Stack

| Layer | Tool |
|---|---|
| Server and staff web app | Python + Django |
| API (for the mobile app) | Django Ninja |
| Database | PostgreSQL 16 |
| Runtime | Docker + Docker Compose |
| Production | Google Compute Engine VM |
| Mobile app | React Native + Expo, in the separate `kaladrius-app` repository |

## Documentation

All documentation is on the site **https://kaladrius-docs.facchini.eti.br** (source in [`docs/`](docs/), Docusaurus): installation, configuration, the user manual and the project's decisions, in English, Portuguese and Spanish.

## Versions

The version history lives in [`releases.yaml`](releases.yaml) and can also be viewed inside the system and in the app. See [Versioning](https://kaladrius-docs.facchini.eti.br/project/versioning).

## License

Open source under the [Apache License 2.0](LICENSE). The Kaladrius name and logo are not covered by the license (see [NOTICE](NOTICE)). Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

Developed by **Miguel Facchini**.

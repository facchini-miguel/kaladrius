---
sidebar_position: 10
title: Contributing
---

# Contributing

Kaladrius is open source under the **Apache License 2.0**. Bug reports, translations, documentation and code are welcome.

## Reporting a bug or asking for a feature

Open an [issue](https://github.com/facchini-miguel/kaladrius/issues) with what you did, what you expected and what happened, the version (bottom of the page or `/api/v1/versao`) and, if possible, a screenshot. **Never attach real patient data.** Security problems go privately, see [Security](security.md#reporting-a-vulnerability).

## Development environment

Follow the [Quick start](quick-start.md). The code folder is mounted in the container and the server reloads when a file is saved. Then:

```bash
docker compose exec app pytest --cov               # tests (coverage must stay at 90% or more)
docker compose exec app ruff check .               # lint
docker compose exec app ruff format .              # formatting
docker compose exec app python manage.py makemigrations --check
```

## Conventions

- **Domain names in Portuguese** (`Paciente`, `Agendamento`), **comments in English**.
- **Every text on screen** is written in Portuguese in the code and translated in `locale/en` and `locale/es`:
  ```bash
  docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests
  ```
- **Documentation in three languages:** a change to `docs/pt-BR/` also changes `docs/en/` and `docs/es/` in the same commit; the same for this site (`website/`).
- **No inline JavaScript** (the Content Security Policy blocks it): scripts go in `static/js/`.
- **Important decisions** get a record in `docs/<language>/decisions/`.
- **Each version** gets an entry in `releases.yaml`, shown in **What's new**.

## Pull requests

1. Fork, create a branch, make the change with tests.
2. Make sure tests, lint and formatting pass.
3. Open the pull request explaining what and why. By contributing, you agree that your contribution is licensed under Apache 2.0.

## This documentation site

```bash
cd website
npm install
npm start                 # English, http://localhost:3000
npm run start:pt-BR       # Portuguese
npm run build             # all languages, in website/build
```

The user manual is not edited here: it comes from `docs/<language>/manual/`, the same files the system shows in **Help**.

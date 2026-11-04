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
- **Test files named in English**, after what they test (`tests/test_patients.py`, `tests/test_schedule.py`), even when the module they test has a Portuguese name (decision 144).
- **Every text on screen** is written in Portuguese in the code and translated in `locale/en` and `locale/es`:
  ```bash
  docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests
  ```
- **Documentation in three languages:** everything is in this site (`docs/`): a change to a page in `docs/docs/` also changes the same page in `docs/i18n/pt-BR/` and `docs/i18n/es/`, in the same commit.
- **No inline JavaScript** (the Content Security Policy blocks it): scripts go in `static/js/`.
- **Important decisions** get a record in `docs/<language>/decisions/`.
- **Each version** gets an entry in `releases.yaml`, shown in **What's new**.

## Pull requests

1. Fork, create a branch, make the change with tests.
2. Make sure tests, lint and formatting pass.
3. Open the pull request explaining what and why. By contributing, you agree that your contribution is licensed under Apache 2.0.

`main` only takes changes through pull requests, merged once the `tests` and `docs` checks pass (decision 141); no approving review is required. On a pull request from someone who is not a collaborator of the repository (usually from a fork), CI only starts after a maintainer clicks "Approve and run workflows", so its checks may wait a while.

## Database migrations

A change to a model needs its migration (`python manage.py makemigrations`), committed with it; CI fails otherwise. Migrations run by themselves when the new version starts. When a pull request adds one, CI comments on it with the SQL each migration runs in production, the operations that need attention, the already applied migrations it edits or deletes, and a test that each one can be undone and applied again (`python manage.py relatorio_migracoes`).

The automatic rollback of the server (decision 135) puts the previous code back but never undoes a migration. So do not drop or rename a column the current version uses in one step: first release a version that stops using it, and only then the migration that drops it. A new required column has the same problem: the previous version's inserts leave it out, so give it `null=True` or a `db_default` (a Python `default` only fills the rows that already exist). And never edit a migration that is already in `main`: production does not run it again; write a new one. `--testar-volta` undoes migrations, so it only runs on a throwaway database (the test one, or `BANCO_DESCARTAVEL=1`, as in CI).

## Dependencies

The libraries the system uses directly are listed in `requirements.in` (the test and lint tools in `requirements-dev.in`). `requirements.txt` and `requirements-dev.txt` are **generated** from them with every dependency, indirect ones included, pinned to an exact version and a hash, so CI and the production image install exactly the same thing, and pip refuses a package whose hash does not match. Do not edit the `.txt` files by hand: change the `.in` file and regenerate them (needs Docker; it uses the Python of `.python-version`):

```bash
deploy/gerar_lock.sh
```

CI runs `deploy/gerar_lock.sh --verificar` and fails while a lock does not match its `.in` file. Dependabot updates both files in its pull requests, indirect libraries included.

The locks are resolved for Linux, where the system runs. On Windows, `pip install` refuses them (a package only Windows needs, such as `colorama`, has no hash in them): develop in Docker ([Quick start](quick-start.md)) or in WSL.

## This documentation site

It needs Node.js 26, the version the image builds it with (`docs/Dockerfile`).

```bash
cd docs
npm install
npm start                 # English, http://localhost:3000
npm run start:pt-BR       # Portuguese
npm run build             # all languages, in docs/build
```

The user manual is not edited here: it comes from `docs/<language>/manual/`, the same files the system shows in **Help**.

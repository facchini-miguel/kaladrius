# Phase 1 plan: staff web app + test data

🇺🇸 English | [🇧🇷 Português](../pt-BR/plano-fase-1.md)

> Status: **in progress**. Steps 1, 2 and 3 completed (versions 0.1.0, 0.2.0 and 0.3.0).

## Goal
Have the staff web app running on **local Docker** with **the same features as the legacy system**, already multi-tenant and secure, with fake test data and the What's new page. Target version: **0.7.0** (each step with new features bumps the minor number). 1.0.0 is reserved for the first real-world use.

## Out of scope for phase 1
API and app (phase 2), patient login (phase 3), plans and billing (phase 4), cloud deploy (right after phase 1), finance, clinical records.

## Project structure

```
medical-system/
├── docker-compose.yml        db (postgres:16) + app
├── Dockerfile
├── .env.example
├── pyproject.toml            dependencies, version, ruff and pytest config
├── releases.yaml
├── config/                   settings (single file, configured via .env), urls, api, wsgi
├── apps/
│   ├── core/                 Clinica, Usuario, Vinculo, roles, current-clinic middleware, audit
│   ├── referencias/          UF, Cidade, Banco, EstadoCivil (global) + initial load
│   ├── pacientes/            Paciente (individual/company), search, record
│   ├── profissionais/        Profissional
│   ├── agenda/               TipoAtendimento, Agendamento, weekly grid, recurrence, conflicts
│   ├── rechamadas/           Rechamada
│   ├── aniversariantes/      lookup by month
│   └── novidades/            reads releases.yaml, What's new page, version in the footer
├── templates/                base layout (Bootstrap 5 + HTMX), permission-aware menu
├── tests/
└── docs/
```

## Steps

| # | Step | Deliverable | Version |
|---|---|---|---|
| 1 ✅ | **Skeleton** | Django project, Docker Compose (Postgres + app), settings via `.env`, Ruff, pytest, GitHub CI, login, home page, `admin` user. Pulled forward from step 7: What's new page, version in the footer and `/api/v1/releases` API | 0.1.0 |
| 2 ✅ | **Multi-tenancy and permissions** | Clinica, Vinculo, roles (clinic admin, front desk, practitioner), fail-closed per-clinic isolation, permission matrix, clinic switcher, admin restricted to superusers, isolation tests. Pulled forward from step 3: **Practitioners** (the first clinic data, used to test isolation end to end) and the first part of the `popular_dados_teste` command | 0.2.0 |
| 3 ✅ | **Reference data and simple records** | States and cities (official IBGE list), banks (Banco Central), marital status, loaded by migration with accent-insensitive search. Per-clinic appointment types, with the 10 original types and colors created automatically for every new clinic. Records menu. State → city endpoint for the patient form | 0.3.0 |
| 4 | **Patients** | Paginated list, search (name, ID, CPF/CNPJ), single individual/company form with CPF/CNPJ validation, chained state → city (HTMX), record with age, delete with confirmation | 0.4.0 |
| 5 | **Schedule** | Weekly grid per practitioner (FullCalendar), hours and slot length configurable per clinic, colors and legend, create/edit/delete in a modal, weekly recurrence N times, conflict blocking (server validation + database constraint), optional patient, the day's recalls and birthdays | 0.5.0 |
| 6 | **Recalls and birthdays** | Recall CRUD. Birthdays by month with a link to the patient record | 0.6.0 |
| 7 | **What's new** (remaining) | "New version: see what changed" notice until the user opens it, filter by module | 0.7.0 |
| 8 | **Test data** | `manage.py popular_dados_teste` command: 2 clinics, ~1,200 fake patients (valid but fake CPF/CNPJ), practitioners, ~5,000 appointments around the current date, recalls, one user per role | 0.7.0 |
| 9 | **Quality** | Test coverage of critical rules (isolation, conflicts, permissions), `check --deploy` with no warnings, change auditing | 0.7.0 |

## Business rules (automatically tested)
- A user only sees and changes data from the clinics they are linked to.
- Appointments of the same practitioner cannot overlap (including recurrences: if one occurrence conflicts, none is saved and the screen shows which date conflicted).
- Times aligned to the clinic's slot length (default 30 min).
- CPF/CNPJ is valid and unique within the clinic.
- Permissions control both the screen (buttons) and the server (the request is blocked).

## New tools (all permissively licensed)
Django, Django Ninja (installed in phase 1 for the releases endpoint), psycopg, argon2-cffi, django-axes (login attempt limiting), django-htmx, PyYAML, Faker (test data), pytest-django, Ruff. Front end: Bootstrap 5, HTMX and FullCalendar as static files (no Node build).

## Verification
1. `docker compose up` → system at `http://localhost:8000`.
2. `docker compose exec app python manage.py popular_dados_teste` → fake data loaded.
3. Log in as `admin` and as one user per role, checking that the menu and buttons follow the permissions.
4. Schedule: create with recurrence, trigger a conflict, edit, delete, switch practitioner and week.
5. A user from clinic A cannot access a patient from clinic B, not even by typing the URL.
6. `docker compose exec app pytest` and `ruff check` passing.
7. What's new page showing the versions from `releases.yaml`.

## Assumptions adopted (the owner asked to proceed without confirming each step)
1. Multi-tenant from now on (decision 012).
2. Address as text fields + state/city, without the legacy district and street tables.
3. Patient finance fields (balance, payment date, bank details) out of phase 1.
4. Optional patient on appointments, keeping the free-text description.

Any of these can be revisited; record the change in `decisions/`.

---
sidebar_position: 8
title: Architecture
---

# Architecture

```
                          ┌── Web (Django templates + HTMX) ─── clinic team
Django + PostgreSQL ──────┤
(one back end)            └── API /api/v1 (Django Ninja) ───┬── App for practitioners and staff (planned)
                                                            └── App for patients (planned)
```

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 |
| Framework | Django, with Django Ninja for the API |
| Database | PostgreSQL 16 (constraints such as "no two appointments at the same time" live in the database) |
| Pages | Server-rendered templates, HTMX for partial updates, Bootstrap 5, FullCalendar for the schedule |
| Application server | Gunicorn (2 processes × 4 threads, sized for 1 GB of RAM) |
| HTTPS | Caddy with automatic Let's Encrypt certificates |
| Packaging | Docker image; Docker Compose for development and production |
| Languages | Django translations (`locale/`): Portuguese, English and Spanish |
| Tests | pytest with coverage (the build fails below 90%) |

## Code

```
config/           settings, URLs, API
apps/
  core/           clinics, users, memberships, permissions, home page
  agenda/         schedule and attendance
  pacientes/      patients
  orcamentos/     estimates and price list
  rechamadas/     recalls and birthdays
  financeiro/     receivables, payables, cash, banks, commissions
  equipe/         team management
  profissionais/  practitioners
  auditoria/      audit log
  monitoramento/  server health
  novidades/      versions and "What's new"
  ajuda/          user manual inside the system
  legado/         import from the previous PHP system
  referencias/    states, cities and other reference data
templates/, static/, locale/
deploy/           production compose, Caddyfile, server scripts
docs/             technical documentation, decisions and the user manual
website/          this documentation site
```

Code names follow the domain in **Portuguese** (`Paciente`, `Agendamento`), with comments in English. Each clinic's data carries a `clinica` key, and the managers filter by the clinic in use.

## Decisions

Every important technical and product decision is recorded, with date and reason, in [docs/en/decisions](https://github.com/facchini-miguel/kaladrius/blob/main/docs/en/decisions/README.md).

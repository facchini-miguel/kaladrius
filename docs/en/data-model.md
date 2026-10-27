# Data model

🇺🇸 English | [🇧🇷 Português](../pt-BR/modelo-de-dados.md)

Entity and field names are kept in Portuguese, as in the code. See the glossary in [README.md](README.md).

## Multi-tenancy principle
- Every piece of clinic data has a `clinica` key. No query runs without filtering by the current clinic.
- The filter is applied centrally (middleware + managers), not by hand in each screen.
- **Fail closed:** every clinic model inherits from `ModeloDaClinica` (`apps/core/isolamento.py`). Its default manager filters by the current clinic and, when no clinic is set, **raises an error instead of returning data**. The filter is decided **when the query runs** (not when it is built), so form fields can be declared over clinic data. Saving or deleting another clinic's row also raises. Platform code that needs every clinic (Django admin, management commands) opts in explicitly with `sem_isolamento()`.
- The current clinic comes from the session and is only honored if the user has an active membership in it (or is a superuser). The Django admin is restricted to platform superusers.
- Public reference tables (state, city, bank, marital status) are **global**, shared by all clinics.

## Entities

### Platform
| Entity | Main fields | Notes |
|---|---|---|
| `Clinica` | name, document (CPF/CNPJ), contact, active, schedule settings (start, end, slot length) | The tenant |
| `Usuario` | login, name, email, password (Argon2), active | Django user |
| `Vinculo` | user, clinic, role, active | A user can work at more than one clinic |

### Roles and permissions (replaces `sist_pessoasgrupos` / `sist_modulosperm`)
| Role | Legacy equivalent | Default access |
|---|---|---|
| Platform superuser | MASTER | Everything, in every clinic |
| Clinic administrator | ADMINISTRADOR | Everything within their own clinic |
| Front desk | — | Schedule, patients, recalls, birthdays |
| Practitioner | — | Schedule and patients. Currently sees and changes the schedule of **every** practitioner in the clinic; limiting it to their own schedule is part of the matrix review |

Each role gets `view`, `create`, `change` and `delete` permissions per module. The matrix lives in `apps/core/permissoes.py` and applies both on the server (the request is blocked) and on screen (buttons and menus are hidden). A detailed review is planned after phase 1, as agreed.

| Module | Administrator | Front desk | Practitioner |
|---|---|---|---|
| Patients | all | view, create, change | view, create, change |
| Schedule | all | all | view, create, change |
| Recalls | all | all | view, create, change |
| Birthdays | all | view | view |
| Practitioners | all | view | view |
| Reference tables | all | view | view |
| Clinic users | all | — | — |
| Clinic settings | all | — | — |
| Audit | view | — | — |

The "Clinic users" and "Clinic settings" modules are already in the matrix but have no screen yet: for now the superuser handles them in the Django admin (see the open items in [phase-1-plan.md](phase-1-plan.md)).

### Clinic
| Entity | Main fields | Legacy table |
|---|---|---|
| `Paciente` (patient) | clinic, type (individual/company), name, company name, CPF/CNPJ, ID card, state registration, sex, marital status, birth date, occupation, guardian, phones (home, work, mobile), email, address (postal code, state, city, district, street, number, complement), notes, active, created/updated timestamps | `pessoas` |
| `Profissional` (practitioner) | clinic, name, professional license (CRO/CRM…), color, active, user (optional) | `dentistas` |
| `TipoAtendimento` (appointment type) | clinic, name, color, active | `agenda_cor` (Surgery, Prosthetics…) |
| `Agendamento` (appointment) | clinic, practitioner, type, start and end (date and time), patient (optional), description, series (recurrence), created by | `agendax` |
| `Rechamada` (recall) | clinic, patient, date, description, done, created by | `agenda` (is_rechamada) |

### Reference (global)
`UF` (state), `Cidade` (city; source: IBGE), `Banco` (bank; source: Central Bank public list), `EstadoCivil` (marital status).

### System
| Entity | Purpose |
|---|---|
| Releases | Read from `releases.yaml` (not stored in the database). See [versioning-and-releases.md](versioning-and-releases.md) |
| `RegistroAuditoria` (audit log) | Who created, changed or deleted what and when (LGPD) |

## Schedule
- `Agendamento` stores start and end as timezone-aware datetimes. Appointments of the same weekly recurrence share the `serie` field.
- Rules: times aligned to the clinic's slot length and within opening hours; no overlap for the same practitioner (back-to-back slots are allowed).
- Overlaps are checked in the form (with a message saying who conflicts) **and** by a PostgreSQL exclusion constraint (`btree_gist`), which holds even when two people save at the same time.

## Audit log (LGPD)
- `RegistroAuditoria` (`apps/auditoria`) stores **who**, **when**, **from which IP**, **which action** and, for changes, the **before and after** of each field.
- Recorded automatically (Django signals): create, change and delete of Paciente, Agendamento, Rechamada, Profissional, TipoAtendimento, Clinica, Vinculo and Usuario. Also: opening a patient record, log in, log out and refused login attempts.
- **Never** stores passwords or their hash (a password change only shows as "changed").
- Entries keep clinic and user ids without a hard foreign key: history survives deleting a user or clinic. They cannot be edited or deleted (read-only admin).
- **Records > Audit** screen, clinic administrator only, filtered by the current clinic. Logins do not belong to a clinic and are shown only to superusers, in the admin.

## Documents and formats
- CPF, CNPJ, phones and postal codes are stored **without punctuation** and formatted only for display (filters in `apps/core/templatetags/formatos.py`).
- CNPJ accepts the Receita Federal **alphanumeric format** (in force since July 2026: letters in the first 12 positions, numeric check digits). Validation in `apps/core/validadores.py`.
- CPF/CNPJ is optional (e.g., children), but **unique within the clinic** when given.

## Intentional differences from the legacy system
| Before | Now | Reason |
|---|---|---|
| Dentist | Practitioner | Generic system |
| Fixed schedule colors | Appointment types configurable per clinic | Each specialty has its own |
| Appointment with free text only | **Optional** linked patient + description | Groundwork for the patient app, keeping quick entry |
| Hand-maintained district and street tables | Address in text fields + state and city from the IBGE table | Less maintenance. Postal code lookup comes later |
| Balance, payment date, bank, branch and account on the patient | **Out of phase 1** | They belong to a future finance module |
| MSN, homepage, fax | Removed | Obsolete |
| `0000-00-00` dates | Optional fields (NULL) | Integrity |
| No foreign keys | Foreign keys and indexes | Integrity and performance |

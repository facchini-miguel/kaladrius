# Data model (phase 1 proposal)

🇺🇸 English | [🇧🇷 Português](../pt-BR/modelo-de-dados.md)

Entity and field names are kept in Portuguese, as in the code. See the glossary in [README.md](README.md).

## Multi-tenancy principle
- Every piece of clinic data has a `clinica` key. No query runs without filtering by the current clinic.
- The filter is applied centrally (middleware + managers), not by hand in each screen.
- **Fail closed:** every clinic model inherits from `ModeloDaClinica` (`apps/core/isolamento.py`). Its default manager filters by the current clinic and, when no clinic is set, **raises an error instead of returning data**. Saving or deleting another clinic's row also raises. Platform code that needs every clinic (Django admin, management commands) opts in explicitly with `sem_isolamento()`.
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
| Practitioner | — | Own schedule and patients |

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

### Clinic
| Entity | Main fields | Legacy table |
|---|---|---|
| `Paciente` (patient) | clinic, type (individual/company), name, company name, CPF/CNPJ, ID card, state registration, sex, marital status, birth date, occupation, guardian, phones (home, work, mobile), email, address (postal code, state, city, district, street, number, complement), notes, active, created/updated timestamps | `pessoas` |
| `Profissional` (practitioner) | clinic, name, professional license (CRO/CRM…), color, active, user (optional) | `dentistas` |
| `TipoAtendimento` (appointment type) | clinic, name, color | `agenda_cor` (Surgery, Prosthetics…) |
| `Agendamento` (appointment) | clinic, practitioner, type, date, start, end, patient (optional), description, series (recurrence), created by | `agendax` |
| `Rechamada` (recall) | clinic, patient, date, description, done | `agenda` (is_rechamada) |

### Reference (global)
`UF` (state), `Cidade` (city; source: IBGE), `Banco` (bank; source: Central Bank public list), `EstadoCivil` (marital status).

### System
| Entity | Purpose |
|---|---|
| Releases | Read from `releases.yaml` (not stored in the database). See [versioning-and-releases.md](versioning-and-releases.md) |
| `RegistroAuditoria` (audit log) | Who created, changed or deleted what and when (LGPD) |

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

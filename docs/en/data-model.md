# Data model

🇺🇸 English | [🇧🇷 Português](../pt-BR/modelo-de-dados.md) | [🇪🇸 Español](../es/modelo-de-datos.md)

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
| `Usuario` | login, name, email, password (Argon2), active, language | Django user |
| `Vinculo` | user, clinic, role, active | A user can work at more than one clinic |

### Roles and permissions (replaces `sist_pessoasgrupos` / `sist_modulosperm`)
| Role | Legacy equivalent | Default access |
|---|---|---|
| Platform superuser | MASTER | Everything, in every clinic |
| Clinic administrator | ADMINISTRADOR | Everything within their own clinic |
| Front desk | — | Schedule, patients, recalls, birthdays |
| Practitioner | — | Schedule and patients. Sees and changes **only their own schedule**: that of the practitioner record linked to their user in Records > Practitioners (decision 044). Without a linked record the schedule is empty, with a notice |

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
| Receipts (receivables, receive, receipt, debtors) | all | view, create, change | — |
| Finance (categories, accounts; payables and cash flow in 0.16) | all | — | — |
| Estimates (approving also needs Receipts) | all | view, create, change | view, create, change |

The "Clinic users" module is the **Records > Team** screen (version 0.8.0): the administrator creates accounts already linked to the clinic, changes roles, sets passwords and removes access (the membership becomes inactive; accounts are never deleted, because of the audit log). Nobody changes their own role, and the clinic never ends up without an active administrator. Name, e-mail and password can only be changed when the account is used **only** in this clinic and is not a superuser: this way a clinic cannot take over someone's access to other clinics. "Clinic settings" is the **Records > Clinic settings** screen (version 0.10.0): name, CPF/CNPJ, e-mail, phone, schedule hours and slot length. A change of hours or slot length that would leave a **future** appointment outside the grid or off the slots is refused, and the screen says which one (past appointments may have other hours).

### Clinic
| Entity | Main fields | Legacy table |
|---|---|---|
| `Paciente` (patient) | clinic, type (individual/company), name, company name, CPF/CNPJ, ID card, state registration, sex, marital status, birth date, occupation, guardian, phones (home, work, mobile), email, address (postal code, state, city, district, street, number, complement), notes, active, archived (with when and by whom), created/updated timestamps | `pessoas` |
| `Profissional` (practitioner) | clinic, name, professional license (CRO/CRM…), color, active, user (optional) | `dentistas` |
| `TipoAtendimento` (appointment type) | clinic, name, color, active | `agenda_cor` (Surgery, Prosthetics…) |
| `Agendamento` (appointment) | clinic, practitioner, type, start and end (date and time), patient (optional), description, series (recurrence), created by | `agendax` |
| `Rechamada` (recall) | clinic, patient, date, description, done, created by | `agenda` (is_rechamada) |

### Reference (global)
`UF` (state), `Cidade` (city; source: IBGE), `Banco` (bank; source: Central Bank public list), `EstadoCivil` (marital status).

### Finance (version 0.15.0)
| Entity | Main fields | Notes |
|---|---|---|
| `Conta` (account) | clinic, name, type (cash, bank, card machine), initial balance (0.16.0), active | Where the money goes. Every clinic starts with Caixa (cash) and Banco (bank) |
| `Categoria` (category) | clinic, name, type (income, expense), active | Every clinic starts with 3 income and 8 expense categories; administrators add others |
| `Lancamento` (entry) | clinic, type (receivable, payable), description, category, patient (optional) or payer as text, practitioner (optional), total, date, notes, cancelled (with reason, when and who), created by | Never deleted: cancelled |
| `Parcela` (installment) | clinic, entry, number, due date, amount | Paid amount and balance are computed from the payments |
| `Pagamento` (payment) | clinic, installment, date, amount received, interest and late fee (included in the amount), discount (administrators only), method (cash, Pix, debit, credit, transfer, boleto, check), account, card brand, installments and transaction code, note, reversed (with reason, when and who), received by | Deducted from the installment: amount − interest + discount. Never stores the card number |

| `Caixa` (cash drawer) | clinic, account, opened at/by, amount counted at opening, closed at/by, expected and counted amounts at closing, note | Daily cash (0.17.0). One open per account; the expected amount is stored at closing, so later reversals do not change a closed drawer |
| `MovimentoCaixa` (drawer movement) | clinic, drawer, type (withdrawal, top-up), amount, other account (optional), reason, created by | A withdrawal to another account (bank deposit) moves the balance between accounts; without another account, the money leaves or enters the system and shows in the cash flow |

Payables (0.16.0) use the same entities, with the supplier in the payer field. Each account's balance is the initial balance plus money in minus money out (non-reversed payments). Amounts are `Decimal` with 2 places. The installment row is locked when receiving, so two people cannot pay the same installment beyond its balance. When a patient is permanently deleted, their entries stay (accounting history) with the payer "Paciente excluído (código N)", and their audit entries lose the personal data.

### Estimates (version 0.18.0)
| Entity | Main fields | Notes |
|---|---|---|
| `Procedimento` (procedure) | clinic, name, price, income category, active | The clinic's price list |
| `Orcamento` (estimate) | clinic, patient, practitioner, date, validity, status (open, approved, refused), discount (administrators only), notes, receivable, approved or refused at/by, created by | Once approved, it becomes a receivable `Lancamento` and no longer changes |
| `ItemOrcamento` (estimate item) | clinic, estimate, procedure (optional), description, teeth (FDI, comma-separated), surfaces or region, quantity, unit price | Description and price copied from the list at the time; changing the list does not change estimates |

When a patient is permanently deleted, their estimates are deleted (teeth are health data) and their audit entries lose the personal data.

### System
| Entity | Purpose |
|---|---|
| Releases | Read from `releases.yaml` (not stored in the database). See [versioning-and-releases.md](versioning-and-releases.md) |
| `RegistroAuditoria` (audit log) | Who created, changed or deleted what and when (LGPD) |
| `Backup` | Each daily backup sent to Cloud Storage, recorded by the server. If the newest is older than 26 hours, superusers see a warning at the top of every screen |

## Schedule
- `Agendamento` stores start and end as timezone-aware datetimes. Appointments of the same weekly recurrence share the `serie` field.
- Rules: times aligned to the clinic's slot length and within opening hours; no overlap for the same practitioner (back-to-back slots are allowed).
- Overlaps are checked in the form (with a message saying who conflicts) **and** by a PostgreSQL exclusion constraint (`btree_gist`), which holds even when two people save at the same time.

## Audit log (LGPD)
- `RegistroAuditoria` (`apps/auditoria`) stores **who**, **when**, **from which IP**, **which action** and, for changes, the **before and after** of each field.
- Recorded automatically (Django signals): create, change and delete of Paciente, Agendamento, Rechamada, Profissional, TipoAtendimento, Clinica, Vinculo and Usuario. Also: opening a patient record, log in, log out and refused login attempts.
- **Never** stores passwords or their hash (a password change only shows as "changed").
- Entries keep clinic and user ids without a hard foreign key: history survives deleting a user or clinic. They cannot be edited or deleted (read-only admin), with one exception: refused login attempts, which hold the username typed, are deleted after 30 days by the `aplicar_retencao` command, run daily by the server together with the backup (decision 045). In the backups they last another 30 days. When a patient is permanently deleted, their entries lose the personal data (see below).
- The record type name is always stored in Portuguese, whatever the user's language: filters and anonymization rely on it.
- **Records > Audit** screen, clinic administrator only, filtered by the current clinic. Changes to user accounts (which do not belong to a clinic) are filed under the clinic where they were made. Logins do not belong to a clinic and are shown only to superusers, in the admin.

## User language
`Usuario.idioma` stores the chosen language (`pt-br`, `en`, `es` or empty to follow the browser). It is not audited, like the last version seen.

## Patient record
Shows identification, contact, notes, the next and the latest 10 appointments (version 0.12.0; for practitioners, only those in their own schedule, linking to the week in the schedule) and the recalls.

## Inactive, archived and deleted patients (version 0.9.0)
- **Inactive:** stopped coming, but still visible to the whole team ("Inactive" filter). Not shown in birthdays.
- **Archived** (replaces the everyday "delete", decision 046): the patient leaves the team's lists, search, schedule (suggestions), birthdays and recalls. Nothing is deleted: appointments, recalls and audit entries stay, and past appointments still show the name. Only the clinic administrator archives, sees archived patients (patient list, Status: Archived) and restores them. An archived patient's CPF/CNPJ stays reserved; the screen says to ask for the restore.
- **Permanently deleted:** only from an archived patient, by the administrator, when the patient asks for their data to be erased (LGPD, art. 18). The record and recalls are deleted, appointments lose the patient, and the audit entries of the patient and of their appointments and recalls lose the personal data (`apps/auditoria/registro.py`, `anonimizar`): who, what, when, the code and the field names remain. The screen reminds that the clinic may be required to keep clinical records (Law 13.787/2018).

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

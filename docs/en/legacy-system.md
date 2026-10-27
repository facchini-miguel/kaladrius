# Legacy system (Odonto System)

🇺🇸 English | [🇧🇷 Português](../pt-BR/sistema-legado.md)

Reference for the rewrite. The old (PHP) code and the backups live **outside the repository**, in the local folder `~/medical-system-old_data/` (owner-only access). The full analysis (in Portuguese) is at `~/medical-system-old_data/legado-php/ANALISE_SISTEMA.md`.

> The backups hold real patient data (LGPD). **Never** copy anything from there into the repository, Docker images or tests, which use **fake data** only. For safety, `old_data/` stays in `.gitignore` and `.dockerignore`.

## Summary
- PHP 5.3 with no framework, MySQL 5.5 (MyISAM, latin1), jQuery 1.x. Written in 2009–2010, used until Nov/2019.
- ~20k lines, ~110 pages, 17 tables.
- Does not run on current PHP (`mysql_*` was removed in PHP 7).

## Features to reproduce (parity)
| Module | Behavior to keep |
|---|---|
| Login | Username + password. Inactive users cannot log in. Home page shows user and group |
| Permissions | Per group and menu item: view, create, change, delete. Buttons follow the permissions |
| People | Individual/company, chained address (state → city → district → street), 4 phones, notes, active. Alphabetical paginated list, search by name, ID and CPF/CNPJ. View, change, delete with confirmation. Calculated age |
| Schedule | Mon–Sun week, 07:30–20:00, 30-min slots, per dentist (chosen in a select and remembered in the session). `<<`/`>>` navigation and "go to date". Block colored by type. Color legend. Clicking an empty slot opens the form (dentist, type, start, end, date, description). "Happens N times" weekly recurrence. Times only at :00/:30. A time conflict for the same dentist blocks saving. Edit and delete on the block. Recall and birthday icons at the bottom of each day |
| Recalls | Person + date + description. List, create, change. Shown on the schedule |
| Birthdays | List by month (name + date) with a link to the record |
| Dentists | CRUD (name) |
| Reference tables | State, city, district, street, bank, address type, marital status |
| System | User and group CRUD, regeneration of default permissions |

## Parity review (2026-10-26)
All 185 PHP files were compared with the new system.
- **Reproduced:** everything in the table above including user management, which arrived in version 0.8.0 (Team screen, with fixed roles instead of configurable groups; decision 040). District, street and address type became text fields (see [data-model.md](data-model.md)).
- **There was no finance module:** no cash flow, receivables or estimates. Only the balance, payment date and bank/branch/account fields in `pessoas`, plus free-text notes. Confirmed in every dump (2011–2019, always the same 17 tables) and in the archives (`www*.rar` hold the same 185 PHP files). A finance module, if any, will be built from scratch.
- **Intentionally not ported** (dead code in the legacy system): related people (the target page never existed), `config_imp.php` (not linked from any screen) and the `rg_obs` field.

## Data import (version 0.8.0)
The `importar_legado` command (`apps/legado`) reads the MySQL dump directly (no MySQL needed) and creates everything in a new clinic at once: if anything fails, nothing is saved. It refuses to import into a clinic that already has patients.

```bash
docker compose exec -T app python manage.py importar_legado - --clinica "Clinic name" \
  < ~/medical-system-old_data/backup_20191106/facchini07_20191106.sql
```

| Legacy system | New system |
|---|---|
| `dentistas` | Practitioners (without the leading `_` the legacy system used for sorting) |
| `agenda_cor` | The clinic's appointment types, matched by name (accent-insensitive) |
| `pessoas` | Patients. The city is matched to the IBGE list by name; district and street become text; the lost leading zero of CPFs is restored; the registration date is kept |
| `agendax` | Appointments, with the description only, as in the legacy system (no linked patient). Those without a description (blocked slots such as "Ocupado") get the type name, since the schedule requires a patient or a description |
| `agenda` (recalls) | Recalls. Past ones are imported as done, since the legacy system had no "done" flag |
| Users and groups | Not imported: the team is created in **Records > Team** |

- Anything without a field of its own goes into the patient's **notes**, in a "[Sistema antigo]" block: legacy code, balance, last payment date, bank/branch/account, fax, website, MSN, plus documents, e-mails, postal codes and cities that could not be used (invalid or repeated CPF/CNPJ, for example). Nothing is discarded.
- Phone numbers without an area code are kept as they were: the clinic had patients with area codes 51 and 54, so it cannot be guessed.
- Overlapping appointments or ones without a practitioner are skipped, and an end before the start becomes 30 minutes. If appointments fall outside the schedule hours, the clinic's hours are widened. The command prints a report counting each case, and the import is recorded in the clinic's audit log.

Result with the 2019-11-06 dump, in the **local** environment (2026-10-27): 1,093 patients, 18,590 appointments (2010–2020), 41 recalls and 2 practitioners. Left out: 1 appointment without a practitioner and 1 recall of a deleted patient; 37 invalid or repeated CPF/CNPJ went to the notes; the schedule now goes until 22:00. **Production:** imported on 2026-10-27 into "Clínica Sorriso", with the same result, after deleting the fake data (`remover_dados_teste`). The data is hosted in the US, by the owner's decision (see LGPD in [architecture.md](architecture.md)); the procedure is in [deploy.md](deploy.md).

## Original appointment types (test seed)
Liberado (free) `#b9f1a7` · Cirurgia (surgery) `#f7a5a5` · Dentística (restorative) `#f6f7a5` · Periodontia (periodontics) `#7b88cb` · Consulta Inicial (first visit) `#e7a5f7` · Prótese (prosthetics) `#fed27d` · Endodontia (endodontics) `#e96cd9` · Ortodontia (orthodontics) `#a7eef1` · Atendimento de 15 em 15 (15-minute visits) `#d5dae6` · Ocupado (busy) `#a7bef1`

## Problems the rewrite solves
Widespread SQL injection (including login), write scripts without login checks, unsalted MD5 passwords, credentials in code, XSS, no CSRF protection, hidden errors, duplicated code, no tests, non-responsive layout.

# Legacy system (Odonto System)

🇺🇸 English | [🇧🇷 Português](../pt-BR/sistema-legado.md)

Reference for the rewrite. The old (PHP) code lives in the local folder `old_data/legado-php/www/`, which is ignored by Git and Docker. The full analysis (in Portuguese) is at `old_data/legado-php/ANALISE_SISTEMA.md`.

> Backups with real patient data are in `old_data/` (local machine only). **Never** remove it from `.gitignore` or copy anything from there into versioned code. This project uses **fake data** only.

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

## Original appointment types (test seed)
Liberado (free) `#b9f1a7` · Cirurgia (surgery) `#f7a5a5` · Dentística (restorative) `#f6f7a5` · Periodontia (periodontics) `#7b88cb` · Consulta Inicial (first visit) `#e7a5f7` · Prótese (prosthetics) `#fed27d` · Endodontia (endodontics) `#e96cd9` · Ortodontia (orthodontics) `#a7eef1` · Atendimento de 15 em 15 (15-minute visits) `#d5dae6` · Ocupado (busy) `#a7bef1`

## Problems the rewrite solves
Widespread SQL injection (including login), write scripts without login checks, unsalted MD5 passwords, credentials in code, XSS, no CSRF protection, hidden errors, duplicated code, no tests, non-responsive layout.

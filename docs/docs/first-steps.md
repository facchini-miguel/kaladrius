---
sidebar_position: 5
title: First steps
---

# First steps

A## 3. Hand it over to the clinic

From here on, the clinic's administrator does everything inside the system, without `/admin/`:

| Step | Where | Manual |
|---|---|---|
| Clinic details and schedule hours | **Records > Clinic settings** | [Clinic settings](manual/clinica.md) |
| Team (front desk, practitioners, administrators) | **Records > Team** | [Team](manual/equipe.md) |
| Practitioners and their schedule colors | **Records > Practitioners** | [Team](manual/equipe.md) |
| Appointment types | **Records > Appointment types** | [Clinic settings](manual/clinica.md) |
| Procedure price list | **Records > Procedure price list** | [Estimates](manual/orcamentos.md) |
| Finance categories and accounts | **Records > Categories** and **Records > Accounts** | [Finance](manual/financeiro.md) |

## Roles

| Role | Can |
|---|---|
| **Administrator** | Everything in the clinic: team, practitioners, settings, payables, cash flow, reports, audit log and archived patients |
| **Front desk** | Every practitioner's schedule, patients, estimates, recalls, receiving and the daily cash |
| **Practitioner** | Only their own schedule, patients, estimates and recalls; no clinic money |

Buttons a person cannot use are not shown. See [Getting started](manual/inicio.md#roles).

## Importing from another system

Kaladrius can import the database of the PHP system it replaces (`python manage.py importar_legado`). For other systems, the import has to be written; see [Contributing](contributing.md).

---
sidebar_position: 5
title: First steps
---

# First steps

After installing, the system has only the **superuser** created by `criar_admin`. The superuser is the support account of the installation: it sees every clinic and the technical pages. Each clinic is then run by its own **administrator**.

## 1. Create the clinic

1. Log in with the superuser and open **`/admin/`** (Django administration).
2. **Clinics > Add**: name and, if you want, CPF/CNPJ, e-mail, phone and address. The schedule hours (start, end, length of each slot) can be changed later by the clinic itself.
3. Save. The clinic starts with default **appointment types** and finance **categories and accounts**, which the clinic can change.

## 2. Create the clinic's administrator

1. **Users > Add**: user name and password.
2. In the user's page, under **Clinic memberships**, add the clinic with the role **Administrator** and keep **active** checked.

A person can work in more than one clinic: add one link per clinic. In the system, they switch clinics by clicking the clinic name in the top bar.

## 3. Hand it over to the clinic

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

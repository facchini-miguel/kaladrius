---
sidebar_position: 5
title: First steps
---

# First steps

After installing, the system has only the **superuser** created by `criar_admin`. The superuser is the support account of the installation: it sees everything in the clinic and the technical pages. The clinic is then run by its own **administrator**.

One installation serves **one clinic**. To serve another clinic, install the system again (another server, or another Compose project on the same one).

## 1. Register the clinic

1. Log in with the superuser. On the first access, the system asks for the clinic: name, **area** (Dentistry, Medicine or another health area) and, if you want, CPF/CNPJ, e-mail, phone and address.
2. Save. The clinic starts with default **appointment types** (dental ones in Dentistry, general ones in the other areas) and finance **categories and accounts**, which the clinic can change. The schedule hours (start, end, length of each slot) and the area are in **Records > Clinic settings**.

## 2. Create the clinic's administrator

In **Records > Team > New member**, create the person with the role **Administrator**. See [Team](manual/equipe.md).

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
| **Practitioner** | Only their own schedule, patients, estimates, recalls and the [medical record](manual/prontuario.md); no clinic money |

Buttons a person cannot use are not shown. See [Getting started](manual/inicio.md#roles).

## Importing from another system

Kaladrius can import the database of the PHP system it replaces (`python manage.py importar_legado`). For other systems, the import has to be written; see [Contributing](contributing.md).

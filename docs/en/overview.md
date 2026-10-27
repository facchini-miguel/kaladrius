# Overview

🇺🇸 English | [🇧🇷 Português](../pt-BR/visao-geral.md) | [🇪🇸 Español](../es/vision-general.md)

## What it is
A management system for clinics (dental, medical, physiotherapy, psychology, etc.) with:
- a **web app** for the clinic staff (front desk, management, practitioners);
- a **mobile app** (Android and iOS) for practitioners and patients.

## Audience

| Who | Where | What they do |
|---|---|---|
| Front desk / clinic management | Web | Schedule, records, recalls, reports, users |
| Practitioner (dentist, doctor…) | Web and app | Own schedule, patient records |
| Patient | App | Own appointments, request a slot, reminders (phase 3) |
| Platform administrator | Web (admin) | Clinics, plans, support |

## Modules (parity with the legacy system)

1. **Patients:** individual or company, documents, address, contacts, notes. Search by name, ID and CPF/CNPJ (Brazilian tax IDs).
2. **Schedule:** weekly grid per practitioner with configurable slots (default 30 min), color per appointment type, weekly recurrence, conflict blocking, and the day's recalls and birthdays highlighted.
3. **Recalls:** follow-up reminders (patient + date + description).
4. **Birthdays:** lookup by month.
5. **Practitioners:** the professionals who see patients (formerly "Dentists").
6. **Reference tables:** states, cities, banks, marital status, appointment types and colors.
7. **Users and permissions:** per-clinic roles with view, create, change and delete permissions per module. The clinic administrator manages the team in Records > Team (0.8.0).
8. **What's new:** version history viewable in the system and in the app.
9. **Audit:** who created, changed, deleted or viewed what, and when (LGPD).
10. **Languages:** Portuguese, English and Spanish, chosen by each user (0.13.0).
11. **Help:** user manual in the three languages inside the system; technical documentation for superusers only (0.14.0).

## Business model (under study)
- **Free** app in the stores.
- **Paid** web subscription for clinics, with more features.
- That is why the system is **multi-tenant** from the start.

## Phases

| Phase | Deliverable |
|---|---|
| **1** ✅ | Staff web app with feature parity + fake test data + local Docker. Completed in 0.7.0 and deployed on Google Cloud |
| Finance | Receivables and payables, payments, debtors, cash flow and daily cash (see [financial-plan.md](financial-plan.md)) |
| 2 | API + app for practitioners and staff |
| 3 | App for patients (own login, appointments, slot requests, push) |
| 4 | Plans, billing, clinic self-service signup, terms (commercial launch) |
| Future | WhatsApp reminders, clinical records, estimates and commission, address lookup by postal code |

---
slug: /
sidebar_position: 1
title: What is Kaladrius
---

# Kaladrius

**Kaladrius** is an open-source system to run a clinic: schedule, patient records, estimates, recalls and finance, in the browser, for **dentists and physicians**. One installation serves one clinic or many, each with its own data, team and settings.

> In medieval bestiaries, the *kaladrius* (Greek *kharadriós*) was a white bird kept by kings: it looked at a sick person, took the illness upon itself and flew away with it towards the sun. The name is a promise of care.

## What it does

| Module | Highlights |
|---|---|
| **Home** | Summary of the day: who is booked, who came, who missed, recalls, birthdays, cash of the day and, for administrators, the result of the day and of the month |
| **Schedule** | Day, week and month views per practitioner, conflict checks, attendance (came / missed / cancelled) |
| **Patients** | Individuals and companies, CPF/CNPJ checks, contact and address, notes, appointments and recalls in the record; active, inactive and archived patients |
| **Estimates** | Procedure price list, printing, approval turns the estimate into receivables |
| **Recalls and birthdays** | Who to call today, overdue recalls, birthdays with the phone number at hand |
| **Finance** | Receivables in instalments, receipts, debtors, daily cash, payables, cash flow, reports, bank statement (OFX) reconciliation, commissions |
| **Team and permissions** | Roles for administrator, front desk and practitioner; a practitioner sees only their own schedule and no clinic money |
| **Audit log** | Who created, changed, deleted or opened each record, when and from where |
| **Privacy** | Built for the Brazilian LGPD: privacy policy, access log, data retention, permanent deletion of archived patients |

The interface is available in **English, Portuguese and Spanish**; each user picks their language.

## How it is built

A single Python/Django application with PostgreSQL, server-rendered pages with HTMX (no heavy front end), an HTTP API for the future mobile apps, and Docker images for installation. It runs comfortably on a **1 GB RAM** virtual machine, such as the Google Cloud free tier. See [Architecture](architecture.md).

## Where to go next

- **Try it on your computer in 5 minutes:** [Quick start](quick-start.md)
- **Install it for a clinic:** [Requirements](installation/requirements.md), then [your own server](installation/docker-compose.md) or the [Google Cloud free tier](installation/google-cloud.md)
- **Learn to use it:** [User manual](manual/inicio.md)

## License

Kaladrius is open source under the **Apache License 2.0**: you can use, change and redistribute it, including commercially. See [Contributing](contributing.md).

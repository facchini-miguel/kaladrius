---
sidebar_position: 7
title: Security and privacy
---

# Security and privacy

Kaladrius stores health data, the most sensitive kind of personal data. This page sums up what the system does and what the installation must do.

## In the system

| Protection | How |
|---|---|
| **Separate clinics** | Every query is limited to the clinic in use; a person only reaches the clinics they are linked to |
| **Roles** | Administrator, front desk and practitioner; a practitioner sees only their own schedule and no clinic money |
| **Passwords** | Stored with Argon2; at least 10 characters, not common, not only numbers, not similar to the user name |
| **Login lockout** | 5 wrong passwords for the same user from the same address block it for 1 hour |
| **Sessions** | Up to 8 hours, ending when the browser closes; cookies `HttpOnly` and, with `DJANGO_SECURE=1`, `Secure` |
| **HTTPS** | Automatic certificate (Caddy); with `DJANGO_SECURE=1`, redirect to HTTPS and HSTS for one year |
| **Content Security Policy** | Only the system's own scripts run; no CDN, no inline JavaScript |
| **Audit log** | Who created, changed, deleted or opened each record, when and from which address; cannot be changed |
| **Uploads** | Limited to 6 MB |
| **API docs** | `/api/v1/docs` only for superusers |

## Privacy (LGPD)

- **Privacy policy** in the system, at `/privacidade/`, in the three languages: what is processed, for what, on what legal basis, who has access, where it is stored, for how long and the patient's rights. Adapt it to your clinic: the clinic is the data controller. See [Privacy policy](manual/privacidade.md).
- **Archived patients** leave the lists and searches; the administrator can **permanently delete** a patient who asks for it, keeping the schedule and the finance without their identity. See [Patients](manual/pacientes.md).
- **Retention:** refused login attempts are deleted after 30 days; backups on Google Cloud after 30 days.
- **No tracking:** only the session and security cookies; no analytics, no third-party scripts.

## What the installation must do

- Keep `.env` readable only by root, with a long `DJANGO_SECRET_KEY` and strong passwords. Never commit it.
- Run with `DJANGO_DEBUG=0`, `DJANGO_SECURE=1` and `DJANGO_PROXY_REVERSO=1` behind Caddy.
- Never run `popular_dados_teste` on a server with real data (its users share one password).
- Expose only ports 80 and 443. The database and the app listen only inside the server.
- Restrict SSH (keys only; on Google Cloud, only through the IAP tunnel).
- Back up every day, keep a copy away from the server, encrypt it and [test restoring it](operations/backup-restore.md).
- Know where the data is: a server outside Brazil is an international transfer under the LGPD (art. 33).
- Keep the system [up to date](operations/upgrade.md).

## Reporting a vulnerability

Please do **not** open a public issue. Report it privately through [GitHub Security Advisories](https://github.com/facchini-miguel/medical-system/security/advisories/new), with the steps to reproduce it. You will get an answer within a few days.

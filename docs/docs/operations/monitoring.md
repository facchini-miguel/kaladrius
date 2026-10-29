---
sidebar_position: 3
title: Monitoring
---

# Monitoring

## Is it up?

`GET /api/v1/versao` answers, without login, with the installed version:

```bash
curl https://clinic.example.com/api/v1/versao
# {"versao": "0.24.1"}
```

Use it in any uptime monitor (UptimeRobot, Healthchecks, Uptime Kuma…) to be warned when the system stops answering.

## Alerts by e-mail or phone (Google Cloud installation)

The server can warn you by itself through [Healthchecks.io](https://healthchecks.io) (free plan: 20 checks), which works with the IPv6-only server:

1. Create an account and one check for each line below (all with the **Simple** schedule). Choose how to be warned: e-mail, Telegram, Signal, a phone notification…
2. Add their addresses to the server `.env` and you are done (the scripts read them on the next run). Any line can be left out.

| Variable in `.env` | Check | Period / grace | Warns when |
|---|---|---|---|
| `MONITOR_SISTEMA_URL` | System up | 5 min / 10 min | The system, opened through the internet by its address (the first name in `SITE_HOSTNAME`), does not answer, or its database does not (`/api/v1/saude`) |
| `MONITOR_BACKUP_URL` | Daily backup | 1 day / 2 h | The daily backup fails or does not run |
| `MONITOR_DEMONSTRACAO_URL` | Demo reset (demo server only) | 1 day / 2 hours | The nightly demo reset (07:30 UTC) fails or does not run |
| `MONITOR_RESTAURACAO_URL` | Backup restore | 7 days / 1 day | The weekly restore test (Sundays, 07:00 UTC: the newest backup restored into a throwaway database) fails |
| `MONITOR_ATUALIZACAO_URL` | Automatic update | 5 min / 15 min | The automatic updates fail or stop running |
| `MONITOR_RECURSOS_URL` | Disk and memory | 5 min / 15 min | Memory, swap or disk reach the critical level |
| `MONITOR_CERTIFICADO_URL` | HTTPS certificate | 1 day / 2 h | The certificate has less than 14 days left (Caddy renews it about 30 days before) |
| `MONITOR_DOCS_URL` | Documentation up | 5 min / 10 min | This documentation site, when the server runs it (`DOCS_HOSTNAME`), does not answer |

You are warned when a signal reports a failure or **stops arriving**, which also covers the whole server being off. Without these variables, nothing is sent.

## Warnings inside the system

Superusers see a warning at the top of every page when:

| Warning | When | Setting |
|---|---|---|
| **Backup** | No backup recorded in the last 26 hours, or none ever | `DJANGO_BACKUP_MONITORADO` |
| **Server health** | The health samples stopped, or memory, swap or disk reached the critical level | `DJANGO_SAUDE_MONITORADA` |

## System health (Google Cloud installation)

Every 5 minutes, `deploy/servidor/saude.sh --coletar` reads CPU, memory, swap, disk, network, load and the memory and CPU of each container, and appends a line to `/opt/kaladrius/saude/amostras.jsonl` (7 days kept, about 1.5 MB). Everyone sees it in **Help > System health**, with charts of the last hours and days; the database tables and the server command are shown to superusers only. The app only reads the file; it has no access to Docker.

On the server, `sudo /opt/kaladrius/bin/saude.sh` prints a report: now, last 24 hours, containers and timers.

## Logs

```bash
kaladrius logs -f app      # requests, errors, migrations
kaladrius logs -f caddy    # certificates and access
kaladrius logs -f db       # database
```

## Audit log

What people did inside the system (who created, changed, deleted or opened each record, when and from where) is in **Records > Audit log**, for the clinic administrator. See [Clinic settings](../manual/clinica.md).

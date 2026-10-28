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

1. Create an account and two checks: **system up** (period 5 minutes, grace 10 minutes) and **daily backup** (period 1 day, grace 2 hours). Choose how to be warned: e-mail, Telegram, Signal, a phone notification…
2. Add their addresses to the server `.env` and you are done (the scripts read them on the next run):

   ```bash
   MONITOR_SISTEMA_URL=https://hc-ping.com/<uuid of "system up">
   MONITOR_BACKUP_URL=https://hc-ping.com/<uuid of "daily backup">
   ```

Every 5 minutes, the health timer opens the system **through the internet, by its address** (the first name in `SITE_HOSTNAME`) and signals the result; the backup signals each daily backup, or its failure. You are warned when a signal reports a failure or **stops arriving**, which also covers the whole server being off. Without these variables, nothing is sent.

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

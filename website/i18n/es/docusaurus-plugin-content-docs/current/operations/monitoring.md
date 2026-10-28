---
sidebar_position: 3
title: Monitoreo
---

# Monitoreo

## ¿Está funcionando?

`GET /api/v1/versao` responde, sin ingreso, con la versión instalada:

```bash
curl https://clinica.ejemplo.com/api/v1/versao
# {"versao": "0.24.1"}
```

Úselo en cualquier monitor de disponibilidad (UptimeRobot, Healthchecks, Uptime Kuma…) para recibir un aviso cuando el sistema deje de responder.

## Avisos dentro del sistema

Los superusuarios ven un aviso arriba de las pantallas cuando:

| Aviso | Cuándo | Configuración |
|---|---|---|
| **Backup** | Ningún backup registrado en las últimas 26 horas, o ninguno hasta hoy | `DJANGO_BACKUP_MONITORADO` |
| **Salud del servidor** | La recolección se detuvo, o la memoria, el swap o el disco llegaron al nivel crítico | `DJANGO_SAUDE_MONITORADA` |

## Salud del sistema (instalación en Google Cloud)

Cada 5 minutos, `deploy/servidor/saude.sh --coletar` lee procesador, memoria, swap, disco, red, carga y la memoria y el procesador de cada contenedor, y agrega una línea a `/opt/medical-system/saude/amostras.jsonl` (7 días guardados, unos 1,5 MB). Todos lo ven en **Ayuda > Salud del sistema**, con gráficos de las últimas horas y días; las tablas de la base y el comando del servidor se muestran solo a los superusuarios. La app solo lee el archivo; no tiene acceso a Docker.

En el servidor, `sudo /opt/medical-system/bin/saude.sh` muestra un informe: ahora, últimas 24 horas, contenedores y tareas programadas.

## Logs

```bash
kaladrius logs -f app      # accesos, errores, migraciones
kaladrius logs -f caddy    # certificados y accesos
kaladrius logs -f db       # base de datos
```

## Auditoría

Lo que las personas hicieron dentro del sistema (quién creó, cambió, eliminó o abrió cada registro, cuándo y desde dónde) está en **Registros > Auditoría**, para el administrador de la clínica. Vea [Configuración de la clínica](../manual/clinica.md).

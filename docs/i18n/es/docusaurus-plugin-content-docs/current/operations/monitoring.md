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

## Avisos por correo o celular (instalación en Google Cloud)

El propio servidor puede avisarle mediante [Healthchecks.io](https://healthchecks.io) (plan gratis: 20 verificaciones), que funciona con el servidor solo IPv6:

1. Cree una cuenta y dos verificaciones: **sistema funcionando** (período de 5 minutos, tolerancia de 10 minutos) y **respaldo diario** (período de 1 día, tolerancia de 2 horas). Elija cómo quiere que le avisen: correo, Telegram, Signal, notificación en el celular…
2. Ponga sus direcciones en el `.env` del servidor y listo (los scripts las leen en la próxima ejecución):

   ```bash
   MONITOR_SISTEMA_URL=https://hc-ping.com/<uuid de "sistema funcionando">
   MONITOR_BACKUP_URL=https://hc-ping.com/<uuid de "respaldo diario">
   ```

Cada 5 minutos, el temporizador de salud abre el sistema **por internet, por su dirección** (el primer nombre de `SITE_HOSTNAME`) y envía el resultado; el respaldo envía una señal en cada respaldo diario, o su falla. Se le avisa cuando una señal informa una falla o **deja de llegar**, lo que también cubre el servidor entero apagado. Sin estas variables, no se envía nada.

## Avisos dentro del sistema

Los superusuarios ven un aviso arriba de las pantallas cuando:

| Aviso | Cuándo | Configuración |
|---|---|---|
| **Backup** | Ningún backup registrado en las últimas 26 horas, o ninguno hasta hoy | `DJANGO_BACKUP_MONITORADO` |
| **Salud del servidor** | La recolección se detuvo, o la memoria, el swap o el disco llegaron al nivel crítico | `DJANGO_SAUDE_MONITORADA` |

## Salud del sistema (instalación en Google Cloud)

Cada 5 minutos, `deploy/servidor/saude.sh --coletar` lee procesador, memoria, swap, disco, red, carga y la memoria y el procesador de cada contenedor, y agrega una línea a `/opt/kaladrius/saude/amostras.jsonl` (7 días guardados, unos 1,5 MB). Todos lo ven en **Ayuda > Salud del sistema**, con gráficos de las últimas horas y días; las tablas de la base y el comando del servidor se muestran solo a los superusuarios. La app solo lee el archivo; no tiene acceso a Docker.

En el servidor, `sudo /opt/kaladrius/bin/saude.sh` muestra un informe: ahora, últimas 24 horas, contenedores y tareas programadas.

## Logs

```bash
kaladrius logs -f app      # accesos, errores, migraciones
kaladrius logs -f caddy    # certificados y accesos
kaladrius logs -f db       # base de datos
```

## Auditoría

Lo que las personas hicieron dentro del sistema (quién creó, cambió, eliminó o abrió cada registro, cuándo y desde dónde) está en **Registros > Auditoría**, para el administrador de la clínica. Vea [Configuración de la clínica](../manual/clinica.md).

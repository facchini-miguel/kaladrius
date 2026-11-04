---
sidebar_position: 1
title: Actualización
---

# Actualización

Kaladrius sigue el [versionado semántico](https://semver.org/lang/es/): `MAYOR.MENOR.CORRECCIÓN`. Cada versión aparece, con lo que cambió, en **Novedades** dentro del sistema y en las [releases de GitHub](https://github.com/facchini-miguel/kaladrius/releases). Las migraciones de la base se ejecutan solas cuando la app inicia.

## Paquete Linux

Con el repositorio de paquetes (agregado a mano, o por el `.deb` o `.rpm` descargado al instalarse), con las actualizaciones del propio sistema: `sudo apt update && sudo apt upgrade`, `sudo dnf upgrade` o `sudo zypper update`. En Arch Linux y CachyOS, o sin el repositorio, descargue el paquete de la versión nueva en la [página de releases](https://github.com/facchini-miguel/kaladrius/releases) e instálelo sobre el instalado (`sudo apt install ./kaladrius_X.Y.Z-1_amd64.deb`, `sudo dnf install ./kaladrius-X.Y.Z-1.x86_64.rpm`). Tiene la misma vuelta automática que la instalación en Google Cloud (abajo): una versión que no responde en 5 minutos se deshace y la anterior sigue en marcha; `sudo kaladrius status` lo muestra. Vea [Paquete Linux](../installation/linux-package.md#actualizaciones).

## Servidor propio

```bash
cd /opt/kaladrius
sudo git pull                              # o: sudo git checkout v0.25.0
sudo docker build -t kaladrius:latest .
kaladrius up -d
kaladrius logs -f app                      # espere "Booting worker" y salga con Ctrl+C
```

Haga un [backup](backup-restore.md) antes de actualizar; es el único camino de vuelta si algo sale mal.

## Instalación en Google Cloud

Nada que hacer: la VM instala cada imagen nueva publicada por el CI en hasta 5 minutos. Para instalar ahora:

```bash
sudo /opt/kaladrius/bin/update.sh --force
```

**Vuelta automática:** después de levantar una versión nueva, la VM espera hasta 5 minutos que el sistema responda la página de salud (`/api/v1/health`, con la base). Si no responde, la VM vuelve a poner la versión de la última actualización exitosa (guardada como la imagen `app:previous`) con su Compose y su Caddyfile, así que una imagen nueva de Caddy o de PostgreSQL también se deshace, registra la nueva como rechazada, para no instalarla de nuevo hasta que salga una versión más nueva, y el monitor "actualización automática" avisa de la falla hasta entonces. `--force` vuelve a intentar la versión rechazada. Una migración que la versión nueva ya aplicó no se deshace: si la versión anterior no funciona con ella, restaure el backup.

## Volver a una versión anterior

Las migraciones no se deshacen. Una versión anterior solo funciona si las migraciones nuevas son compatibles con ella (por ejemplo, solo agregaron tablas y campos). El camino seguro es restaurar el backup hecho antes de la actualización.

En el servidor propio:

```bash
cd /opt/kaladrius
sudo git checkout v0.24.1
sudo docker build -t kaladrius:latest .
kaladrius up -d
```

En Google Cloud, detenga antes la actualización automática, o la VM vuelve a la imagen más nueva en 5 minutos:

```bash
sudo systemctl stop kaladrius-update.timer
cd /opt/kaladrius/release
sudo APP_IMAGE=<registro>/app:0.24.1 docker compose -f docker-compose.prod.yml up -d app
# después de publicar la corrección:
sudo systemctl start kaladrius-update.timer
```

Cada versión tiene una etiqueta de imagen `X.Y.Z` que nunca cambia.

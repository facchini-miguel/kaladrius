---
sidebar_position: 1
title: Actualización
---

# Actualización

Kaladrius sigue el [versionado semántico](https://semver.org/lang/es/): `MAYOR.MENOR.CORRECCIÓN`. Cada versión aparece, con lo que cambió, en **Novedades** dentro del sistema y en las [releases de GitHub](https://github.com/facchini-miguel/kaladrius/releases). Las migraciones de la base se ejecutan solas cuando la app inicia.

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
sudo /opt/kaladrius/bin/atualizar.sh --forcar
```

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
sudo systemctl stop kaladrius-atualizar.timer
cd /opt/kaladrius/release
sudo IMAGEM_APP=<registro>/app:0.24.1 docker compose -f docker-compose.prod.yml up -d app
# después de publicar la corrección:
sudo systemctl start kaladrius-atualizar.timer
```

Cada versión tiene una etiqueta de imagen `X.Y.Z` que nunca cambia.

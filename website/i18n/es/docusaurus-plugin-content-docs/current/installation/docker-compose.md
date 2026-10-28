---
sidebar_position: 2
title: Servidor propio (Docker Compose)
---

# Servidor propio (Docker Compose)

Esta guía instala Kaladrius en cualquier servidor Linux con Docker: una VPS, una máquina en la clínica o una VM en la nube. Ejecuta tres contenedores:

| Contenedor | Qué hace |
|---|---|
| `caddy` | Recibe los accesos en los puertos 80 y 443, obtiene el certificado HTTPS solo y los reenvía a la app |
| `app` | Kaladrius (Django + Gunicorn), accesible solo desde el propio servidor (`127.0.0.1:8000`) |
| `db` | PostgreSQL 16, con los datos en un volumen de Docker |

Revise antes los [requisitos](requirements.md): el dominio ya debe apuntar al servidor, y los puertos 80 y 443 deben estar abiertos.

## 1. Instale Docker y Git

En Debian 13:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git
sudo systemctl enable --now docker
```

En Ubuntu, el paquete del plugin Compose se llama `docker-compose-v2` en lugar de `docker-compose`. Verifique con `docker compose version`.

Para otras distribuciones, vea la [documentación de Docker](https://docs.docker.com/engine/install/).

## 2. Descargue el código

```bash
sudo git clone https://github.com/facchini-miguel/medical-system.git /opt/kaladrius
cd /opt/kaladrius
```

## 3. Configure

```bash
sudo cp .env.example .env
sudo chmod 600 .env
sudo nano .env
```

Cambie estos valores (la lista completa está en [Configuración](../configuration.md)):

```ini
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<un valor aleatorio largo>
DJANGO_ALLOWED_HOSTS=clinica.ejemplo.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://clinica.ejemplo.com
DJANGO_SECURE=1
DJANGO_PROXY_REVERSO=1

POSTGRES_PASSWORD=<una contraseña fuerte>

DJANGO_ADMIN_USERNAME=admin
DJANGO_ADMIN_PASSWORD=<una contraseña fuerte>

# Usado por Caddy para el certificado HTTPS
SITE_HOSTNAME=clinica.ejemplo.com
# La imagen construida en el paso 4
IMAGEM_APP=kaladrius:latest
# La recolección de la salud del servidor solo existe en la instalación de Google Cloud
DJANGO_SAUDE_MONITORADA=0
```

Para generar valores aleatorios: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.

:::tip
Deje `DJANGO_BACKUP_MONITORADO` activado (el valor predeterminado): los superusuarios ven un aviso arriba de las pantallas cuando no se registró ningún backup en las últimas 26 horas. [Backup y restauración](../operations/backup-restore.md) muestra cómo programar backups que se registran solos.
:::

## 4. Construya la imagen

```bash
sudo docker build -t kaladrius:latest .
```

## 5. Inicie el sistema

Los comandos de abajo usan el archivo de producción `deploy/docker-compose.prod.yml` con su `.env`. Para escribir menos, cree un atajo:

```bash
alias kaladrius='sudo docker compose -p kaladrius --env-file /opt/kaladrius/.env -f /opt/kaladrius/deploy/docker-compose.prod.yml'
```

(Agregue la línea a `~/.bashrc` para conservarla.) Luego:

```bash
kaladrius up -d
kaladrius ps
```

La app aplica las migraciones de la base de datos cada vez que inicia. Caddy pide el certificado a Let's Encrypt en el primer acceso; puede tardar un minuto.

## 6. Cree el administrador

```bash
kaladrius exec app python manage.py criar_admin
```

Abra `https://clinica.ejemplo.com`, ingrese y siga los [Primeros pasos](../first-steps.md) para crear la clínica y el equipo.

## Comandos útiles

```bash
kaladrius ps                                   # estado de los contenedores
kaladrius logs -f app                          # log de la app (Ctrl+C para salir)
kaladrius logs -f caddy                        # problemas de HTTPS y de acceso
kaladrius exec app python manage.py <comando>  # comandos de Django
kaladrius restart app                          # reiniciar después de cambiar el .env
kaladrius down                                 # detener (los datos quedan)
```

A continuación: [Actualización](../operations/upgrade.md) y [Backup y restauración](../operations/backup-restore.md).

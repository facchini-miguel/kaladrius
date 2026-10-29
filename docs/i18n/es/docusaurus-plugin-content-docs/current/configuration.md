---
sidebar_position: 4
title: Configuración
---

# Configuración

Todo lo que cambia de una instalación a otra está en el archivo **`.env`**, junto al código (servidor propio) o en `/opt/kaladrius/.env` (Google Cloud). Contiene contraseñas: déjelo legible solo por root (`chmod 600`) y nunca lo ponga en Git.

Después de cambiarlo, reinicie: `kaladrius up -d` (se recrean los contenedores cuya configuración cambió).

## Django

| Variable | Predeterminado | Qué hace |
|---|---|---|
| `DJANGO_SECRET_KEY` | **obligatoria** | Firma sesiones y tokens. Un valor aleatorio largo; cambiarlo cierra la sesión de todos |
| `DJANGO_DEBUG` | `0` | `1` muestra los detalles de los errores. **Nunca `1` en un servidor** |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Dominios a los que responde el sistema, separados por coma |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vacío | Los mismos dominios con `https://`, separados por coma |
| `DJANGO_SECURE` | `0` | `1` activa las protecciones de HTTPS: redirige a HTTPS, cookies seguras, HSTS de un año. Use `1` en un servidor |
| `DJANGO_PROXY_REVERSO` | `0` | `1` cuando está detrás de Caddy (u otro proxy): toma la IP del visitante de `X-Forwarded-For`, para la auditoría y el bloqueo de ingreso |
| `DJANGO_DEMONSTRACAO` | desactivado | Solo en el servidor de la demostración pública: activa el reinicio diario de la demostración (decisión 086). Nunca en el servidor de una clínica |
| `DJANGO_BACKUP_MONITORADO` | activado cuando `DJANGO_DEBUG=0` | Avisa a los superusuarios cuando no se registró ningún backup en las últimas 26 horas |
| `DJANGO_SAUDE_MONITORADA` | activado cuando `DJANGO_DEBUG=0` | Avisa a los superusuarios cuando la recolección de la salud del servidor se detiene o un recurso queda crítico. Use `0` fuera de la instalación de Google Cloud |
| `DJANGO_SAUDE_DIR` | `/saude` | Carpeta, dentro del contenedor, con las muestras de salud |
| `DJANGO_DOCS_URL` | `https://kaladrius-docs.facchini.eti.br` | Este sitio de documentación. El menú **Ayuda** lo abre en el idioma del usuario |

## Base de datos

| Variable | Predeterminado | Qué hace |
|---|---|---|
| `POSTGRES_DB` | `kaladrius` | Nombre de la base |
| `POSTGRES_USER` | `kaladrius` | Usuario de la base |
| `POSTGRES_PASSWORD` | vacío | Contraseña de la base. Use una fuerte |
| `POSTGRES_HOST` | `localhost` | `db` con Docker Compose |
| `POSTGRES_PORT` | `5432` | |

El contenedor de la base crea la base y el usuario con estos valores la primera vez que inicia. Cambiarlos después no modifica una base que ya existe.

## Primer administrador

Usadas solo por `python manage.py criar_admin`, que no hace nada si el usuario ya existe.

| Variable | Predeterminado | Qué hace |
|---|---|---|
| `DJANGO_ADMIN_USERNAME` | `admin` | Nombre de usuario del superusuario |
| `DJANGO_ADMIN_PASSWORD` | **exigida por el comando** | Contraseña del superusuario |
| `DJANGO_ADMIN_EMAIL` | vacío | E-mail del superusuario |

Después del primer ingreso, puede quitar `DJANGO_ADMIN_PASSWORD` del archivo.

## Producción

| Variable | Predeterminado | Qué hace |
|---|---|---|
| `SITE_HOSTNAME` | **obligatoria** | Dominio(s) que Caddy atiende y para los que obtiene el certificado HTTPS, separados por coma, p. ej. `clinica.ejemplo.com, www.clinica.ejemplo.com` |
| `IMAGEM_APP` | el registro de la instalación de referencia | Imagen Docker de la app, p. ej. `kaladrius:latest` cuando la construye usted |

## Solo para desarrollo

| Variable | Qué hace |
|---|---|
| `DJANGO_SEED_PASSWORD` | Contraseña de los usuarios ficticios creados por `popular_dados_teste`. **Nunca** ejecute ese comando en un servidor con datos reales: todos los usuarios ficticios comparten esta contraseña |

## Configuración fija

Está en `config/settings.py` y vale para todas las instalaciones:

- **Zona horaria** `America/Sao_Paulo` e **idioma predeterminado** portugués (cada usuario puede cambiar a inglés o español).
- **Sesiones** de hasta 8 horas, que terminan al cerrar el navegador.
- **Bloqueo de ingreso:** 5 contraseñas erróneas para el mismo usuario desde la misma dirección lo bloquean por 1 hora.
- **Envío de archivos** hasta 6 MB (el mayor es un extracto bancario OFX), limitado por Caddy.

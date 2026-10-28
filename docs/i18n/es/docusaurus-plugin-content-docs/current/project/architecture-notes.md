---
sidebar_position: 2
---

# Notas de arquitectura

## Visión general

```
                          ┌── Web (plantillas de Django + HTMX) ─── equipo de la clínica
Django + PostgreSQL ──────┤
(un único back-end)       └── API /api/v1 (Django Ninja) ───┬── App: perfil profesional/equipo
                                                            └── App: perfil paciente
                                                                 + push (Firebase Cloud Messaging)
```

## Repositorios (privados)

| Repositorio | Contenido | Fase |
|---|---|---|
| `kaladrius` (este) | Django, web del equipo, API, Docker, documentación | 1 |
| `kaladrius-app` | React Native + Expo (Android e iOS) | 2 |

Los dos se comunican **solo por la API**.

## Stack del servidor

| Ítem | Elección | Licencia |
|---|---|---|
| Lenguaje | Python 3.13 | PSF |
| Framework | Django (versión estable actual; migrar a la 6.2 LTS en abr/2027) | BSD |
| API | Django Ninja | MIT |
| Base de datos | PostgreSQL 16 | PostgreSQL (permisiva) |
| Interactividad web | HTMX | BSD |
| Calendario de la agenda | FullCalendar (solo plugins gratuitos) | MIT |
| Estilo | Bootstrap 5 | MIT |
| Idiomas | Traducción de Django (gettext); archivos compilados con GNU gettext, solo como herramienta de build | BSD (Django); GPL (herramienta, no es dependencia del código) |
| Documentos en el sistema | Python-Markdown | BSD |
| Servidor de aplicaciones | Gunicorn | MIT |
| Archivos estáticos | WhiteNoise | MIT |
| Límite de intentos de acceso | django-axes | MIT |
| HTTPS / proxy | Caddy | Apache 2.0 |
| Pruebas | pytest + pytest-django | MIT |
| Lint y formato | Ruff | MIT |

Regla: **no usar dependencias GPL/AGPL**, para mantener libre la elección de licencia del proyecto.

## Idiomas (versión 0.13.0, decisión 049)
- La interfaz existe en **portugués** (texto de origen, escrito en el código), **inglés** y **español**. Las traducciones están en `locale/en/` y `locale/es/` (`django.po`); los archivos compilados (`.mo`) no van a Git: se generan en el build de la imagen y en el CI.
- Cada usuario elige el idioma en el menú de banderas de la barra superior (entre la clínica y el nombre del usuario; 0.13.1); la elección queda en el perfil (`Usuario.idioma`) y en una cookie (para la pantalla de acceso). Sin elección, vale el idioma del navegador.
- Las fechas usan los formatos del idioma (`SHORT_DATE_FORMAT`); la agenda usa el idioma correspondiente de FullCalendar; las Novedades tienen cada texto en los tres idiomas.
- Quedan en portugués: los datos (nombres de tipos de atención, descripciones, ciudades), el registro de auditoría y los mensajes de los comandos de terminal.
- El CI falla si algún texto nuevo no se extrajo (`makemessages`) y una prueba falla si falta una traducción.

## Ayuda (versión 0.14.0, decisión 050)
- Menú **Ayuda** con el **manual del usuario** (`docs/<idioma>/manual/`, para todo el equipo, en el idioma del usuario), las **Novedades** y, solo para el superusuario, la **documentación técnica** (el resto de `docs/`, que describe la infraestructura).
- Los archivos Markdown se convierten en HTML en el servidor (`apps/ajuda`). Los enlaces entre documentos se vuelven enlaces dentro del sistema; los demás archivos del repositorio apuntan a GitHub. Solo se abren archivos `.md` dentro de `docs/`.

## Ejecución (Docker Compose)

| Servicio | Local (`docker-compose.yml`) | Producción (`deploy/docker-compose.prod.yml`) |
|---|---|---|
| `db` | postgres:16-alpine, volumen persistente, sin puerto expuesto | Igual, con memoria ajustada para la e2-micro |
| `app` | Imagen construida en la máquina, código montado como volumen, servidor de desarrollo de Django (recarga al guardar) | Imagen de Artifact Registry con Gunicorn, accesible solo en `127.0.0.1:8000` |
| `caddy` | — | caddy:2-alpine en la red del host: HTTPS automático (Let's Encrypt) y proxy hacia la app |

En producción, solo la app recibe el `.env` completo; la base de datos recibe solo las variables de Postgres y Caddy, solo el nombre del sitio. Los nombres de los proyectos son distintos (`medical-system-dev` en local, `medical-system` en la VM), para que los dos nunca compartan contenedores ni volúmenes en la misma máquina. En los dos casos la app ejecuta las migraciones al iniciar y lee la configuración del `.env`. La copia de seguridad no es un servicio de Compose: un *timer* de systemd en la VM ejecuta `deploy/servidor/backup.sh` todos los días (`pg_dump` → Cloud Storage). Detalles en [despliegue.md](production.md).

## Infraestructura

Regla: **solo recursos del free tier de Google Cloud** (decisión 020).

| Entorno | Dónde | Costo |
|---|---|---|
| Local | Docker en la computadora del desarrollador | — |
| Nube (pruebas y producción) | VM **e2-micro** en `us-east1-b`, disco estándar de 30 GB, **solo IPv6 público** (el IPv4 se cobra). Detalles en [despliegue.md](production.md) | Gratis |
| Copias de seguridad | Cloud Storage, bucket regional en EE. UU., hasta 5 GB | Gratis |

**Proyecto en Google Cloud:** `medical-system-facchini`, con la API de Compute Engine activa y una **alerta de presupuesto de R$ 5** (avisos en R$ 0,50, R$ 2,50 y R$ 5) para detectar cualquier cobro.

**Límites del free tier a respetar:** 1 VM e2-micro, 30 GB de disco estándar, 5 GB en Cloud Storage, 1 GB/mes de tráfico de salida. Las instantáneas de disco se cobran, por eso no se usan. El IPv4 público de las VM se cobra, por eso la VM solo tiene IPv6 público (decisión 035).

**CI/CD:** GitHub Actions ejecuta lint y pruebas y publica la imagen en **Artifact Registry** de Google (autenticación sin claves). La VM verifica cada 5 minutos y se actualiza sola (GitHub no tiene IPv6, así que la VM no llegaría a GHCR, ni el CI llegaría a la VM por SSH).

## Seguridad (requisitos)
- Protecciones nativas de Django activas (CSRF, escape de XSS, ORM parametrizado, encabezados de seguridad). `manage.py check --deploy` sin alertas.
- Contraseñas con hash Argon2 y límite de intentos de acceso (django-axes: 5 errores por usuario + IP bloquean durante 1 hora). En IPv6 cuenta la red /48, y no la dirección, porque cambiar de dirección dentro de la propia red es trivial (decisión 041).
- Sin recuperación de contraseña por correo (el servidor no envía correos): cada persona cambia su propia contraseña en el menú con su nombre, y el administrador de la clínica define una nueva en Registros > Equipo (decisión 042).
- Registro de auditoría de cambios, consultas a fichas y accesos al sistema (`apps/auditoria`).
- Detrás de Caddy, la IP real del cliente viene de `X-Forwarded-For` (`DJANGO_PROXY_REVERSO=1`), usada por django-axes y por la auditoría.
- **Aislamiento por clínica** en todas las consultas, con pruebas automáticas que intentan acceder a datos de otra clínica.
- Secretos solo en `.env` (fuera de Git) y en los *Secrets* de GitHub. Push protection activo.
- Postgres sin puerto expuesto. Firewall de la VM: solo TCP 80/443 y UDP 443 (HTTP/3) desde internet; SSH solo por el túnel IAP de Google.
- LGPD: registro de accesos y cambios (auditoría), copias de seguridad en un bucket privado, cifradas en reposo por Google (sin cifrado propio) y eliminadas después de 30 días. Si una copia falla, el servidor lo intenta de nuevo; si la última tiene más de 26 horas, los superusuarios ven un aviso en la web (decisión 043). Los datos quedan en servidores en EE. UU. (exigencia del free tier). Antes del uso real con pacientes, revisar la transferencia internacional de datos (LGPD, art. 33) o migrar a una región en Brasil.

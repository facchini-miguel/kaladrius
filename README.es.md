# Medical System

[🇺🇸 English](README.md) | [🇧🇷 Português](README.pt-BR.md) | 🇪🇸 Español

Sistema de gestión para clínicas: agenda por profesional, registro de pacientes, recordatorios de regreso, cumpleaños, usuarios y permisos. Atiende varias clínicas en el mismo servidor (multiclínica). Interfaz en portugués, inglés y español.

Es la reescritura del antiguo *Odonto System* (PHP 5, 2009–2019), ahora genérico para cualquier tipo de clínica.

[![CI](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml)

**Versión actual: 0.14.0** · [Novedades](releases.yaml) · [Todas las versiones](https://github.com/facchini-miguel/medical-system/releases)

> Estado: **fase 1 concluida** (paridad de funciones con el sistema antiguo), funcionando en https://medical-system.duckdns.org (free tier de Google Cloud, solo IPv6). Ver [docs/es/despliegue.md](docs/es/despliegue.md).

## Ejecutar en local

Requisito: Docker con Docker Compose v2 (el comando `docker compose`).

```bash
cp .env.example .env          # complete las contraseñas y la SECRET_KEY (valores aleatorios)
docker compose up --build -d  # levanta la base de datos y la aplicación
docker compose exec app python manage.py criar_admin   # crea el administrador definido en .env
```

Abra http://localhost:8000. La documentación de la API está en http://localhost:8000/api/v1/docs.

| Tarea | Comando |
|---|---|
| Datos de prueba (clínicas, usuarios y profesionales ficticios, 600 pacientes por clínica, 6 semanas de agenda y recordatorios) | `docker compose exec app python manage.py popular_dados_teste` |
| Compilar las traducciones (después de `git pull` o de cambiar textos; la imagen lo hace en el build) | `docker compose exec app python manage.py compilemessages` |
| Extraer textos nuevos para traducir (`locale/*/LC_MESSAGES/django.po`) | `docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests` |
| Eliminar los datos de prueba (nunca toca clínicas ni usuarios reales) | `docker compose exec app python manage.py remover_dados_teste --confirmar` |
| Importar los datos del antiguo Odonto System en una clínica nueva (ver [docs/es/sistema-heredado.md](docs/es/sistema-heredado.md)) | `docker compose exec -T app python manage.py importar_legado - --clinica "Nombre" < dump.sql` |
| Anonimizar los datos de una clínica para usarlos en pruebas (irreversible) | `docker compose exec app python manage.py anonimizar_clinica --clinica "Nombre" --confirmar` |
| Simular agenda y recordatorios actuales en una clínica de **prueba** | `docker compose exec app python manage.py simular_movimento --clinica "Nombre" --confirmar` |
| Título y texto de la *Release* de GitHub (en inglés) | `docker compose exec app python manage.py notas_release X.Y.Z [--titulo]` |
| Pruebas (con cobertura, mínimo 90 %) | `docker compose exec app pytest --cov` |
| Lint | `docker compose exec app ruff check .` |
| Formatear el código | `docker compose exec app ruff format .` |
| Nueva migración | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Detener | `docker compose down` (los datos de la base quedan en el volumen `medical-system-dev_pgdata`) |

## Stack

| Capa | Herramienta |
|---|---|
| Servidor y web del equipo | Python + Django |
| API (para la app) | Django Ninja |
| Base de datos | PostgreSQL 16 |
| Ejecución | Docker + Docker Compose |
| Producción | VM de Google Compute Engine |
| App | React Native + Expo, en el repositorio separado `medical-system-app` |

## Documentación

Toda la documentación está en [`docs/`](docs/README.md), en portugués ([`docs/pt-BR`](docs/pt-BR/README.md)), inglés ([`docs/en`](docs/en/README.md)) y español ([`docs/es`](docs/es/README.md)). El portugués es el idioma principal; el inglés y el español son traducciones. El manual del usuario también está dentro del sistema, en **Ayuda > Manual del usuario**.

## Versiones

El historial de versiones está en [`releases.yaml`](releases.yaml) y también puede verse dentro del sistema y en la app. Ver [docs/es/versionado-y-versiones.md](docs/es/versionado-y-versiones.md).

## Licencia

Software propietario. Todos los derechos reservados. Ver [LICENSE](LICENSE).

Desarrollado por **Miguel Facchini**.

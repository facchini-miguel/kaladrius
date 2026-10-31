<img src="static/img/logo.svg" alt="" width="72">

# Kaladrius

[🇺🇸 English](README.md) | [🇧🇷 Português](README.pt-BR.md) | 🇪🇸 Español

Sistema de gestión para clínicas: agenda por profesional, registro de pacientes, recordatorios de regreso, cumpleaños, usuarios y permisos. Una instalación atiende a una clínica. Interfaz en portugués, inglés y español.

Es la reescritura del antiguo *Odonto System* (PHP 5, 2009–2019), ahora genérico para cualquier tipo de clínica.

[![CI](https://github.com/facchini-miguel/kaladrius/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/kaladrius/actions/workflows/ci.yml)

**Versión actual: 0.41.1** · [Novedades](releases.yaml) · [Todas las versiones](https://github.com/facchini-miguel/kaladrius/releases)

> Estado: en desarrollo, funcionando como demostración. **Para conocerlo, empiece en https://www.facchini.eti.br/es/kaladrius/**: la página tiene los accesos de demostración de cada perfil (recepción, profesional, financiero, administrador de la clínica), las pantallas y todos los enlaces. La demostración funciona en el free tier de Google Cloud, solo IPv6; ver [Producción de referencia](https://kaladrius-docs.facchini.eti.br/es/project/production).

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
| Datos de prueba (una clínica, usuarios y profesionales ficticios, 600 pacientes, 6 semanas de agenda y recordatorios) | `docker compose exec app python manage.py popular_dados_teste` |
| Compilar las traducciones (después de `git pull` o de cambiar textos; la imagen lo hace en el build) | `docker compose exec app python manage.py compilemessages` |
| Extraer textos nuevos para traducir (`locale/*/LC_MESSAGES/django.po`) | `docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests` |
| Eliminar los datos de prueba (nunca toca clínicas ni usuarios reales) | `docker compose exec app python manage.py remover_dados_teste --confirmar` |
| Importar los datos del antiguo Odonto System en una clínica nueva | `docker compose exec -T app python manage.py importar_legado - --clinica "Nombre" < dump.sql` |
| Anonimizar los datos de una clínica para usarlos en pruebas (irreversible) | `docker compose exec app python manage.py anonimizar_clinica --clinica "Nombre" --confirmar` |
| Simular agenda y recordatorios actuales en una clínica de **prueba** | `docker compose exec app python manage.py simular_movimento --clinica "Nombre" --confirmar` |
| Título y texto de la *Release* de GitHub (en inglés) | `docker compose exec app python manage.py notas_release X.Y.Z [--titulo]` |
| Probar la restauración de una copia (la descarga y la restaura en un PostgreSQL temporal) | `deploy/testar_backup.sh [archivo.dump]` |
| Pruebas (con cobertura, mínimo 90 %) | `docker compose exec app pytest --cov` |
| Lint | `docker compose exec app ruff check .` |
| Formatear el código | `docker compose exec app ruff format .` |
| Nueva migración | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Detener | `docker compose down` (los datos de la base quedan en el volumen `kaladrius-dev_pgdata`) |

## Stack

| Capa | Herramienta |
|---|---|
| Servidor y web del equipo | Python + Django |
| API (para la app) | Django Ninja |
| Base de datos | PostgreSQL 16 |
| Ejecución | Docker + Docker Compose |
| Producción | VM de Google Compute Engine |
| App | React Native + Expo, en el repositorio separado `kaladrius-app` |

## Documentación

Toda la documentación está en el sitio **https://kaladrius-docs.facchini.eti.br/es/** (fuente en [`docs/`](docs/), Docusaurus): instalación, configuración, manual del usuario y las decisiones del proyecto, en español, inglés y portugués.

## Versiones

El historial de versiones está en [`releases.yaml`](releases.yaml) y también puede verse dentro del sistema y en la app. La lista completa, con las notas de cada versión, está en las [Releases de GitHub](https://github.com/facchini-miguel/kaladrius/releases). Ver [Versiones](https://kaladrius-docs.facchini.eti.br/es/project/versioning).

## Licencia

Código abierto bajo la [Licencia Apache 2.0](LICENSE). El nombre y el logo de Kaladrius no forman parte de la licencia (ver [NOTICE](NOTICE)). Las contribuciones son bienvenidas: ver [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) y el [Código de Conducta](CODE_OF_CONDUCT.md).

Desarrollado por **Miguel Facchini**.

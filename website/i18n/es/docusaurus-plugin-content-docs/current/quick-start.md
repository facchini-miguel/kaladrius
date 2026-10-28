---
sidebar_position: 2
title: Inicio rápido
---

# Inicio rápido

Ejecute Kaladrius en su computadora, con datos ficticios, para conocerlo. Necesita **Git** y **Docker** (Docker Desktop en Windows y macOS; Docker Engine con el plugin Compose en Linux).

:::warning
Esta instalación es **solo para evaluación y desarrollo**: modo de depuración, sin HTTPS, usuarios ficticios con la misma contraseña. Para atender una clínica, siga la [Instalación](installation/requirements.md).
:::

## 1. Descargue el código

```bash
git clone https://github.com/facchini-miguel/medical-system.git kaladrius
cd kaladrius
```

## 2. Cree el archivo de configuración

```bash
cp .env.example .env
```

El ejemplo funciona tal cual en su computadora. Si quiere, cambie las contraseñas (`POSTGRES_PASSWORD`, `DJANGO_ADMIN_PASSWORD`, `DJANGO_SEED_PASSWORD`) y la `DJANGO_SECRET_KEY`. Para generar un valor aleatorio:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 3. Inicie el sistema

```bash
docker compose up --build
```

La primera vez tarda unos minutos (descarga PostgreSQL y construye la imagen). Cuando el log muestre `Starting development server at http://0.0.0.0:8000/`, el sistema está funcionando, pero todavía sin usuarios.

## 4. Cree el administrador y los datos de ejemplo

En otra terminal, en la misma carpeta:

```bash
docker compose exec app python manage.py criar_admin
docker compose exec app python manage.py popular_dados_teste
```

- `criar_admin` crea el **superusuario** con `DJANGO_ADMIN_USERNAME` y `DJANGO_ADMIN_PASSWORD`.
- `popular_dados_teste` crea clínicas ficticias (marcadas "(teste)") con pacientes, agenda, presupuestos y finanzas, y usuarios de prueba para cada perfil, todos con la contraseña `DJANGO_SEED_PASSWORD`.

## 5. Ábralo

Vaya a **http://localhost:8000** e ingrese con el administrador. Use el nombre de la clínica en la barra superior para cambiar entre las clínicas de ejemplo, y la bandera para cambiar el idioma.

## Detener y limpiar

```bash
docker compose down          # detiene; los datos quedan para la próxima vez
docker compose down -v       # detiene y borra la base de datos
```

Para borrar solo los datos ficticios y mantener lo demás: `docker compose exec app python manage.py remover_dados_teste --confirmar`.

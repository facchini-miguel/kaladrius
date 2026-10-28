---
sidebar_position: 2
title: Quick start
---

# Quick start

Run Kaladrius on your computer, with fake data, to look around. You need **Git** and **Docker** (Docker Desktop on Windows and macOS, Docker Engine with the Compose plugin on Linux).

:::warning
This setup is for **evaluation and development only**: debug mode, no HTTPS, fake users that share one password. To serve a clinic, follow [Installation](installation/requirements.md).
:::

## 1. Get the code

```bash
git clone https://github.com/facchini-miguel/medical-system.git kaladrius
cd kaladrius
```

## 2. Create the configuration file

```bash
cp .env.example .env
```

The example works as is on your computer. If you want, replace the passwords (`POSTGRES_PASSWORD`, `DJANGO_ADMIN_PASSWORD`, `DJANGO_SEED_PASSWORD`) and the `DJANGO_SECRET_KEY`. To generate a random value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 3. Start it

```bash
docker compose up --build
```

The first time takes a few minutes (it downloads PostgreSQL and builds the image). When the log shows `Starting development server at http://0.0.0.0:8000/`, the system is ready, but it has no users yet.

## 4. Create the administrator and the sample data

In another terminal, in the same folder:

```bash
docker compose exec app python manage.py criar_admin
docker compose exec app python manage.py popular_dados_teste
```

- `criar_admin` creates the **superuser** from `DJANGO_ADMIN_USERNAME` and `DJANGO_ADMIN_PASSWORD`.
- `popular_dados_teste` creates fictitious clinics (marked "(teste)") with patients, schedule, estimates and finance, and test users for each role, all with the password `DJANGO_SEED_PASSWORD`.

## 5. Open it

Go to **http://localhost:8000** and log in with the administrator. Use the clinic name in the top bar to switch between the sample clinics, and the flag to change the language.

## Stop and clean up

```bash
docker compose down          # stops; the data stays for next time
docker compose down -v       # stops and deletes the database
```

To remove only the fake data and keep everything else: `docker compose exec app python manage.py remover_dados_teste --confirmar`.

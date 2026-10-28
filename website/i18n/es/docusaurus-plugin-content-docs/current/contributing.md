---
sidebar_position: 10
title: Cómo contribuir
---

# Cómo contribuir

Kaladrius es código abierto, bajo la **Licencia Apache 2.0**. Informes de errores, traducciones, documentación y código son bienvenidos.

## Informar un error o pedir una función

Abra un [issue](https://github.com/facchini-miguel/medical-system/issues) con lo que hizo, lo que esperaba y lo que pasó, la versión (en el pie de la página o en `/api/v1/versao`) y, si es posible, una captura de pantalla. **Nunca adjunte datos reales de pacientes.** Los problemas de seguridad van en privado, vea [Seguridad](security.md#cómo-informar-una-vulnerabilidad).

## Entorno de desarrollo

Siga el [Inicio rápido](quick-start.md). La carpeta del código queda montada en el contenedor y el servidor se recarga al guardar un archivo. Luego:

```bash
docker compose exec app pytest --cov               # pruebas (la cobertura debe quedar en 90% o más)
docker compose exec app ruff check .               # lint
docker compose exec app ruff format .              # formato
docker compose exec app python manage.py makemigrations --check
```

## Convenciones

- **Nombres del dominio en portugués** (`Paciente`, `Agendamento`), **comentarios en inglés**.
- **Todo texto de la pantalla** se escribe en portugués en el código y se traduce en `locale/en` y `locale/es`:
  ```bash
  docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests
  ```
- **Documentación en los tres idiomas:** un cambio en `docs/pt-BR/` también cambia `docs/en/` y `docs/es/` en el mismo commit; lo mismo vale para este sitio (`website/`).
- **Sin JavaScript incrustado en la página** (la Content Security Policy lo bloquea): los scripts van en `static/js/`.
- **Las decisiones importantes** reciben un registro en `docs/<idioma>/decisiones/`.
- **Cada versión** recibe una entrada en `releases.yaml`, mostrada en **Novedades**.

## Pull requests

1. Haga un fork, cree una rama y haga el cambio con pruebas.
2. Verifique que pruebas, lint y formato pasen.
3. Abra el pull request explicando qué y por qué. Al contribuir, acepta que su contribución queda bajo la licencia Apache 2.0.

## Este sitio de documentación

```bash
cd website
npm install
npm start                 # inglés, http://localhost:3000
npm run start:es          # español
npm run build             # todos los idiomas, en website/build
```

El manual del usuario no se edita aquí: viene de `docs/<idioma>/manual/`, los mismos archivos que el sistema muestra en **Ayuda**.

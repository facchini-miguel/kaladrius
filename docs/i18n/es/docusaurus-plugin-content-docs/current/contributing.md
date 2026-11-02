---
sidebar_position: 10
title: Cómo contribuir
---

# Cómo contribuir

Kaladrius es código abierto, bajo la **Licencia Apache 2.0**. Informes de errores, traducciones, documentación y código son bienvenidos.

## Informar un error o pedir una función

Abra un [issue](https://github.com/facchini-miguel/kaladrius/issues) con lo que hizo, lo que esperaba y lo que pasó, la versión (en el pie de la página o en `/api/v1/versao`) y, si es posible, una captura de pantalla. **Nunca adjunte datos reales de pacientes.** Los problemas de seguridad van en privado, vea [Seguridad](security.md#cómo-informar-una-vulnerabilidad).

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
- **Documentación en los tres idiomas:** todo está en este sitio (`docs/`): un cambio en una página de `docs/docs/` también cambia la misma página en `docs/i18n/pt-BR/` y `docs/i18n/es/`, en el mismo commit.
- **Sin JavaScript incrustado en la página** (la Content Security Policy lo bloquea): los scripts van en `static/js/`.
- **Las decisiones importantes** reciben un registro en `docs/<idioma>/decisiones/`.
- **Cada versión** recibe una entrada en `releases.yaml`, mostrada en **Novedades**.

## Pull requests

1. Haga un fork, cree una rama y haga el cambio con pruebas.
2. Verifique que pruebas, lint y formato pasen.
3. Abra el pull request explicando qué y por qué. Al contribuir, acepta que su contribución queda bajo la licencia Apache 2.0.

## Migraciones de la base

Un cambio en un modelo necesita su migración (`python manage.py makemigrations`), en el mismo commit; sin ella, el CI falla. Las migraciones se ejecutan solas cuando la versión nueva arranca. Cuando un pull request trae una, el CI comenta en él el SQL que cada migración ejecuta en producción, las operaciones que requieren atención y una prueba de que cada una puede deshacerse y aplicarse de nuevo (`python manage.py relatorio_migracoes`).

La vuelta automática del servidor (decisión 135) vuelve a poner el código anterior, pero nunca deshace una migración. Así que no elimine ni renombre de una vez una columna que la versión actual usa: primero publique una versión que deje de usarla, y solo después la migración que la elimina.

## Dependencias

Las bibliotecas que el sistema usa directamente están en `requirements.in` (las herramientas de prueba y lint en `requirements-dev.in`). `requirements.txt` y `requirements-dev.txt` se **generan** a partir de ellas, con todas las dependencias, incluidas las indirectas, fijadas en una versión exacta y con hash, para que el CI y la imagen de producción instalen exactamente lo mismo, y pip rechaza un paquete cuyo hash no coincide. No edite los `.txt` a mano: cambie el `.in` y vuelva a generarlos (necesita Docker; usa el Python de `.python-version`):

```bash
deploy/gerar_lock.sh
```

El CI ejecuta `deploy/gerar_lock.sh --verificar` y falla mientras un lock no coincida con su `.in`. Dependabot actualiza los dos archivos en sus pull requests, incluidas las bibliotecas indirectas.

Los locks se resuelven para Linux, donde se ejecuta el sistema. En Windows, `pip install` los rechaza (un paquete que solo Windows necesita, como `colorama`, no tiene hash en ellos): desarrolle en Docker ([Inicio rápido](quick-start.md)) o en WSL.

## Este sitio de documentación

Necesita Node.js 26, la versión con la que la imagen lo genera (`docs/Dockerfile`).

```bash
cd docs
npm install
npm start                 # inglés, http://localhost:3000
npm run start:es          # español
npm run build             # todos los idiomas, en docs/build
```

El manual del usuario no se edita aquí: viene de `docs/<idioma>/manual/`, los mismos archivos que el sistema muestra en **Ayuda**.

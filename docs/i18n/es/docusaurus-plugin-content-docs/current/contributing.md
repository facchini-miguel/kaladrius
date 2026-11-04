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
- **Carpetas y módulos de las apps con nombre en inglés** (`apps/patients/`, `apps/core/countries.py`). Cada app mantiene su **label** en portugués (`label = "pacientes"` en `apps.py`), el nombre con el que la conocen las tablas de la base de datos, las migraciones y los permisos, y los archivos de migración mantienen sus nombres: producción los tiene registrados (decisión 145).
- **Archivos de prueba con nombre en inglés**, según lo que prueban (`tests/test_patients.py`, `tests/test_schedule.py`), aunque el módulo probado tenga nombre en portugués (decisión 144).
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

`main` solo recibe cambios por pull request, con merge después de que pasan los checks `tests` y `docs` (decisión 141); no hace falta una revisión que apruebe. En un pull request de quien no es colaborador del repositorio (por lo general, de un fork), el CI solo empieza después de que un mantenedor hace clic en "Approve and run workflows", así que los checks pueden quedar esperando un rato.

## Migraciones de la base

Un cambio en un modelo necesita su migración (`python manage.py makemigrations`), en el mismo commit; sin ella, el CI falla. Las migraciones se ejecutan solas cuando la versión nueva arranca. Cuando un pull request trae una, el CI comenta en él el SQL que cada migración ejecuta en producción, las operaciones que requieren atención, las migraciones ya aplicadas que edita o elimina, y una prueba de que cada una puede deshacerse y aplicarse de nuevo (`python manage.py relatorio_migracoes`).

La vuelta automática del servidor (decisión 135) vuelve a poner el código anterior, pero nunca deshace una migración. Así que no elimine ni renombre de una vez una columna que la versión actual usa: primero publique una versión que deje de usarla, y solo después la migración que la elimina. Una columna obligatoria nueva tiene el mismo problema: los INSERT de la versión anterior la dejan fuera, así que dele `null=True` o un `db_default` (un `default` de Python solo rellena las filas que ya existen). Y nunca edite una migración que ya está en `main`: producción no la ejecuta de nuevo; escriba una nueva. `--testar-volta` deshace migraciones, así que solo se ejecuta en una base desechable (la de pruebas, o con `BANCO_DESCARTAVEL=1`, como en el CI).

## Dependencias

Las bibliotecas que el sistema usa directamente están en `requirements.in` (las herramientas de prueba y lint en `requirements-dev.in`). `requirements.txt` y `requirements-dev.txt` se **generan** a partir de ellas, con todas las dependencias, incluidas las indirectas, fijadas en una versión exacta y con hash, para que el CI y la imagen de producción instalen exactamente lo mismo, y pip rechaza un paquete cuyo hash no coincide. No edite los `.txt` a mano: cambie el `.in` y vuelva a generarlos (necesita Docker; usa el Python de `.python-version`):

```bash
deploy/lock.sh
```

El CI ejecuta `deploy/lock.sh --check` y falla mientras un lock no coincida con su `.in`. Dependabot actualiza los dos archivos en sus pull requests, incluidas las bibliotecas indirectas.

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

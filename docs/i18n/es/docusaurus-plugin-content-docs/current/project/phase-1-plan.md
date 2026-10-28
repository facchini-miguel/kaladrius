---
sidebar_position: 7
---

# Plan de la fase 1: web del equipo + datos de prueba

> Estado: **concluida** en la versión 0.7.0 (26/10/2026).

## Objetivo
Tener, funcionando en **Docker local**, la web del equipo con **las mismas funciones del sistema antiguo**, ya multiclínica, segura, con datos ficticios para pruebas y la página de Novedades. Versión objetivo: **0.7.0** (cada etapa con funciones nuevas sube el número del medio). La 1.0.0 queda para el primer uso real.

## Fuera del alcance de la fase 1
API y app (fase 2), acceso del paciente (fase 3), planes y cobro (fase 4), despliegue en la nube (hecho justo después de la fase 1, ver [despliegue.md](production.md)), financiero, historia clínica.

## Estructura del proyecto

```
medical-system/
├── docker-compose.yml        entorno local: db (postgres:16) + app
├── Dockerfile
├── .env.example
├── pyproject.toml            versión, configuración de ruff, pytest y cobertura
├── requirements*.txt         dependencias (fijadas)
├── releases.yaml
├── config/                   settings (un archivo, configurado por .env), urls, api, wsgi
├── apps/
│   ├── core/                 Clinica, Usuario, Vinculo, perfiles y permisos, aislamiento por clínica, comandos
│   ├── referencias/          UF, Cidade, Banco, EstadoCivil (globales) + carga inicial
│   ├── pacientes/            Paciente (PF/PJ), búsqueda, ficha
│   ├── profissionais/        Profissional
│   ├── agenda/               TipoAtendimento, Agendamento, grilla semanal, repetición, conflictos, cumpleaños
│   ├── rechamadas/           Rechamada
│   ├── auditoria/            RegistroAuditoria, señales, pantalla de auditoría
│   └── novidades/            lectura de releases.yaml, página Novedades, versión en el pie de página
├── templates/                diseño base (Bootstrap 5 + HTMX), menú según los permisos
├── static/                   CSS, JS de la agenda y bibliotecas (Bootstrap, HTMX, FullCalendar)
├── deploy/                   compose de producción, Caddyfile, scripts y timers de la VM
├── tests/
└── docs/
```

## Etapas

| # | Etapa | Entrega | Versión |
|---|---|---|---|
| 1 ✅ | **Esqueleto** | Proyecto Django, Docker Compose (Postgres + app), settings vía `.env`, Ruff, pytest, CI en GitHub, acceso, página de inicio, usuario `admin`. Adelantado de la etapa 7: página Novedades, versión en el pie de página y API `/api/v1/releases` | 0.1.0 |
| 2 ✅ | **Multiclínica y permisos** | Clinica, Vinculo, perfiles (admin de la clínica, recepción, profesional), aislamiento por clínica que falla cerrado, matriz de permisos, selector de clínica, admin restringido al superusuario, pruebas de aislamiento. Adelantado de la etapa 3: registro de **Profesionales** (primer dato de la clínica, usado para probar el aislamiento de punta a punta) y la primera parte del comando `popular_dados_teste` | 0.2.0 |
| 3 ✅ | **Referencias y registros simples** | Estados y ciudades (lista oficial del IBGE), bancos (Banco Central), estado civil, cargados por migración y con búsqueda sin acentos. Tipos de atención por clínica, con los 10 tipos y colores originales creados automáticamente en toda clínica nueva. Menú Registros. Endpoint estado → ciudades para el formulario de pacientes | 0.3.0 |
| 4 ✅ | **Pacientes** | Lista paginada, búsqueda (nombre, código, CPF/CNPJ), formulario único PF/PJ con validación de CPF/CNPJ, estado → ciudad encadenado (HTMX), ficha con edad, eliminación con confirmación. CNPJ alfanumérico (julio/2026) aceptado. Pacientes ficticios en `popular_dados_teste` (Faker) | 0.4.0 |
| 5 ✅ | **Agenda** | Grilla semanal por profesional (FullCalendar), horario y duración configurables por clínica, colores y leyenda, crear/editar/eliminar en un modal, repetición semanal N veces, bloqueo de conflictos (validación en el servidor + restricción en la base), paciente opcional (búsqueda mientras se escribe), cumpleaños del día, eliminación de una cita o de la serie. Restricción en la base (PostgreSQL) contra superposiciones. Los **recordatorios del día** llegan con el módulo de recordatorios (etapa 6) | 0.5.0 |
| 6 ✅ | **Recordatorios y cumpleaños** | Recordatorios (registro, filtros, completar, en la ficha del paciente y en el encabezado de los días de la agenda). Cumpleaños por mes con la edad a cumplir y enlace a la ficha | 0.6.0 |
| 7 ✅ | **Novedades** (resto) | Aviso "versión nueva: vea qué cambió" hasta que el usuario lo abre, filtro por módulo | 0.7.0 |
| 8 ✅ | **Datos de prueba** | Comando `manage.py popular_dados_teste`: 2 clínicas, ~1.200 pacientes ficticios (CPF/CNPJ válidos y falsos), profesionales, ~1.500 citas alrededor de la fecha actual, recordatorios, un usuario por perfil | 0.7.0 |
| 9 ✅ | **Calidad** | Cobertura de pruebas en las reglas críticas (aislamiento, conflicto, permisos), `check --deploy` sin alertas, auditoría de cambios (LGPD), límite de intentos de acceso (django-axes), cobertura medida en el CI (mínimo 90 %; actual 96 %) | 0.7.0 |

## Reglas de negocio (probadas automáticamente)
- Un usuario solo ve y modifica datos de las clínicas a las que está vinculado.
- Las citas del mismo profesional no pueden superponerse (incluso en las repeticiones: si una ocurrencia entra en conflicto, no se guarda ninguna y la pantalla muestra qué fecha chocó).
- Horarios alineados con la duración de la clínica (30 min por defecto).
- El CPF/CNPJ es válido y único dentro de la clínica.
- Los permisos controlan tanto la pantalla (botones) como el servidor (la solicitud se bloquea).

## Herramientas nuevas (todas con licencias permisivas)
Django, Django Ninja (instalado ya en la fase 1 para el endpoint de versiones), psycopg, argon2-cffi, django-axes (límite de intentos de acceso), Gunicorn, WhiteNoise (archivos estáticos), PyYAML, Faker (datos de prueba), pytest-django, pytest-cov, Ruff. En el front: Bootstrap 5, HTMX y FullCalendar como archivos estáticos (sin build de Node).

## Verificación
1. `docker compose up` → sistema en `http://localhost:8000`.
2. `docker compose exec app python manage.py popular_dados_teste` → datos ficticios cargados.
3. Acceso con `admin` y con un usuario de cada perfil, verificando que el menú y los botones cambian según el permiso.
4. Agenda: crear con repetición, provocar un conflicto, editar, eliminar, cambiar de profesional y de semana.
5. Un usuario de la clínica A no accede a un paciente de la clínica B, ni escribiendo la URL.
6. `docker compose exec app pytest` y `ruff check` pasando.
7. Página Novedades mostrando las versiones de `releases.yaml`.

## Supuestos adoptados (el titular pidió seguir sin confirmar cada paso)
1. Multiclínica desde ya (decisión 012).
2. Dirección en campos de texto + estado/ciudad, sin las tablas de barrio y calle del sistema antiguo.
3. Campos financieros del paciente (saldo, fecha de pago, datos bancarios) fuera de la fase 1.
4. Paciente opcional en la cita, manteniendo la descripción libre.

Cualquiera puede revisarse; registrar el cambio en `decisiones/`.

## Pendientes después de la fase 1
La revisión de paridad con el sistema antiguo (ver sistema-heredado.md) mostró que todo se reprodujo, excepto la gestión de usuarios y grupos, que llegó en la 0.8.0.

| Pendiente | Situación |
|---|---|
| Pantalla de gestión del equipo por el administrador de la clínica | ✅ 0.8.0: **Registros > Equipo**, con perfiles fijos (decisión 040) |
| Importar datos reales del sistema antiguo | ✅ 0.8.0: comando `importar_legado` (decisión 039). Importado en producción el 27/10/2026 (Clínica Sorriso) y anonimizado el mismo día, para uso como datos de prueba (decisión 047) |
| Pantalla de configuración de la clínica (horario y duración de la agenda) | ✅ 0.10.0: **Registros > Configuración de la clínica** |
| Revisión de la matriz de permisos (`apps/core/permissoes.py`) | Profesional limitado a su propia agenda (decisión 044). El resto de la matriz sigue igual |
| Prueba de la agenda y los recordatorios en el navegador | Con el titular |
| Logotipo (SVG) | Con el titular |

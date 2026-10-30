---
sidebar_position: 8
title: Arquitectura
---

# Arquitectura

```
                          ┌── Web (plantillas Django + HTMX) ─── equipo de la clínica
Django + PostgreSQL ──────┤
(un solo back end)        └── API /api/v1 (Django Ninja) ───┬── App para profesionales y equipo (planeada)
                                                            └── App para pacientes (planeada)
```

## Tecnologías

| Capa | Elección |
|---|---|
| Lenguaje | Python 3.13 |
| Framework | Django, con Django Ninja para la API |
| Base de datos | PostgreSQL 16 (reglas como "dos citas no ocupan el mismo horario" están en la propia base) |
| Páginas | Plantillas generadas en el servidor, HTMX para actualizar partes de la pantalla, Bootstrap 5, FullCalendar en la agenda |
| Servidor de aplicación | Gunicorn (2 procesos × 4 hilos, dimensionado para 1 GB de RAM) |
| HTTPS | Caddy con certificados automáticos de Let's Encrypt |
| Empaquetado | Imagen Docker; Docker Compose en desarrollo y producción |
| Idiomas | Traducciones de Django (`locale/`): portugués, inglés y español |
| Pruebas | pytest con cobertura (el build falla por debajo del 90%) |

## Código

```
config/           configuración, URLs, API
apps/
  core/           clínicas, módulos activados/desactivados, usuarios, vínculos, permisos, pantalla de inicio
  agenda/         agenda y asistencia
  pacientes/      pacientes
  orcamentos/     presupuestos y tabla de procedimientos
  odontologia/    módulo de odontología (odontograma), solo con la especialidad Odontología activa
  convenios/      convenios y credenciales de los pacientes
  prontuario/     historia clínica: anamnesis de cada consulta y adendas (solo profesionales)
  rechamadas/     recordatorios y cumpleaños
  financeiro/     cuentas por cobrar y por pagar, caja, bancos, comisiones
  equipe/         gestión del equipo
  profissionais/  profesionales
  auditoria/      auditoría
  monitoramento/  salud del servidor
  novidades/      versiones y "Novedades"
  ajuda/          política de privacidad y enlaces a este sitio
  legado/         importación del sistema PHP anterior
  referencias/    estados, ciudades y otros datos de referencia
templates/, static/, locale/
deploy/           compose de producción, Caddyfile, scripts del servidor
docs/             este sitio de documentación: instalación, manual, decisiones
```

Los nombres en el código siguen el dominio en **portugués** (`Paciente`, `Agendamento`), con comentarios en inglés. Los datos de cada clínica llevan la clave `clinica`, y las consultas filtran por la clínica en uso.

## Decisiones

Cada decisión técnica y de producto importante queda registrada, con fecha y motivo, en el [registro de decisiones](project/decisions.md).

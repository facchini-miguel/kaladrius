---
slug: /
sidebar_position: 1
title: Qué es Kaladrius
---

# Kaladrius

**Kaladrius** es un sistema de código abierto para administrar la clínica: agenda, registro de pacientes, presupuestos, recordatorios y finanzas, en el navegador, para **dentistas y médicos**. Una instalación atiende una clínica o varias, cada una con sus datos, equipo y configuración.

> En los bestiarios medievales, el *kaladrius* (del griego *kharadriós*) era un ave blanca criada por los reyes: miraba al enfermo, tomaba la enfermedad para sí y volaba con ella hacia el sol. El nombre es una promesa de cuidado.

## Qué hace

| Módulo | Destacados |
|---|---|
| **Inicio** | Resumen del día: quién está agendado, quién vino, quién faltó, recordatorios, cumpleaños, caja del día y, para el administrador, el resultado del día y del mes |
| **Agenda** | Vistas de día, semana y mes por profesional, control de conflictos, asistencia (asistió / faltó / canceló) |
| **Pacientes** | Persona física y jurídica, validación de CPF/CNPJ, contacto y dirección, notas, citas y recordatorios en la ficha; pacientes activos, inactivos y archivados |
| **Presupuestos** | Tabla de procedimientos, impresión, aprobación que genera las cuentas por cobrar |
| **Recordatorios y cumpleaños** | A quién llamar hoy, recordatorios atrasados, cumpleaños con el celular a mano |
| **Finanzas** | Cuentas por cobrar en cuotas, recibos, deudores, caja del día, cuentas por pagar, flujo de caja, informes, conciliación de extracto bancario (OFX), comisiones |
| **Equipo y permisos** | Perfiles de administrador, recepción y profesional; el profesional ve solo su propia agenda y ningún valor de la clínica |
| **Auditoría** | Quién creó, cambió, eliminó o abrió cada registro, cuándo y desde dónde |
| **Privacidad** | Hecho para la LGPD brasileña: política de privacidad, registro de accesos, retención de datos, eliminación definitiva de pacientes archivados |

La interfaz funciona en **portugués, inglés y español**; cada usuario elige su idioma.

## Cómo está hecho

Una sola aplicación Python/Django con PostgreSQL, páginas generadas en el servidor con HTMX (sin front-end pesado), una API HTTP para las futuras aplicaciones móviles e imágenes Docker para la instalación. Funciona bien en una máquina virtual de **1 GB de RAM**, como la del free tier de Google Cloud. Vea [Arquitectura](architecture.md).

## Por dónde seguir

- **Probarlo en su computadora en 5 minutos:** [Inicio rápido](quick-start.md)
- **Instalarlo para una clínica:** [Requisitos](installation/requirements.md), luego [servidor propio](installation/docker-compose.md) o [free tier de Google Cloud](installation/google-cloud.md)
- **Aprender a usarlo:** [Manual del usuario](manual/inicio.md)

## Licencia

Kaladrius es código abierto, bajo la **Licencia Apache 2.0**: puede usarlo, modificarlo y redistribuirlo, también comercialmente. Vea [Cómo contribuir](contributing.md).

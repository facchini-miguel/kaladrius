---
sidebar_position: 5
title: Primeros pasos
---

# Primeros pasos

D## 3. Entréguelo a la clínica

De aquí en adelante, el administrador de la clínica hace todo dentro del sistema, sin `/admin/`:

| Paso | Dónde | Manual |
|---|---|---|
| Datos de la clínica y horario de la agenda | **Registros > Configuración de la clínica** | [Configuración de la clínica](manual/clinica.md) |
| Equipo (recepción, profesionales, administradores) | **Registros > Equipo** | [Equipo](manual/equipe.md) |
| Profesionales y sus colores en la agenda | **Registros > Profesionales** | [Equipo](manual/equipe.md) |
| Tipos de atención | **Registros > Tipos de atención** | [Configuración de la clínica](manual/clinica.md) |
| Tabla de procedimientos | **Registros > Tabla de procedimientos** | [Presupuestos](manual/orcamentos.md) |
| Categorías y cuentas de finanzas | **Registros > Categorías** y **Registros > Cuentas** | [Finanzas](manual/financeiro.md) |

## Perfiles

| Perfil | Puede |
|---|---|
| **Administrador** | Todo en la clínica: equipo, profesionales, configuración, cuentas por pagar, flujo de caja, informes, auditoría y pacientes archivados |
| **Recepción** | Agenda de todos los profesionales, pacientes, presupuestos, recordatorios, cobros y caja del día |
| **Profesional** | Solo su propia agenda, pacientes, presupuestos y recordatorios; ningún valor de la clínica |

Los botones que la persona no puede usar no aparecen. Vea [Primeros pasos del manual](manual/inicio.md#perfiles).

## Importar desde otro sistema

Kaladrius importa la base del sistema PHP al que reemplaza (`python manage.py importar_legado`). Para otros sistemas, hay que escribir la importación; vea [Cómo contribuir](contributing.md).

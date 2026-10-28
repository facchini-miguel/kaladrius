---
sidebar_position: 5
title: Primeros pasos
---

# Primeros pasos

Después de instalar, el sistema tiene solo el **superusuario** creado por `criar_admin`. El superusuario es la cuenta de soporte de la instalación: ve todas las clínicas y las páginas técnicas. Cada clínica la administra su propio **administrador**.

## 1. Cree la clínica

1. Ingrese con el superusuario y abra **`/admin/`** (administración de Django).
2. **Clínicas > Añadir**: nombre y, si quiere, CPF/CNPJ, e-mail, teléfono y dirección. El horario de la agenda (inicio, fin y duración de cada turno) lo puede cambiar después la propia clínica.
3. Guarde. La clínica empieza con **tipos de atención** y **categorías y cuentas** de finanzas predeterminados, que la clínica puede cambiar.

## 2. Cree el administrador de la clínica

1. **Usuarios > Añadir**: nombre de usuario y contraseña.
2. En la página del usuario, en **Vínculos con clínicas**, agregue la clínica con el perfil **Administrador** y deje **activo** marcado.

Una persona puede trabajar en más de una clínica: agregue un vínculo para cada una. En el sistema, cambia de clínica haciendo clic en el nombre de la clínica en la barra superior.

## 3. Entréguelo a la clínica

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

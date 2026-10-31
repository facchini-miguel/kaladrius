---
sidebar_position: 8
---

# Configuración de la clínica

Estas pantallas son del **administrador de la clínica**, en el menú **Registros**.

## Configuración de la clínica
En **Registros > Configuración de la clínica**: nombre, CPF/CNPJ, correo electrónico y teléfono de la clínica, y el **horario de la agenda** (inicio, fin y duración de cada horario).

La instalación atiende a **una sola clínica**, con un registro de pacientes, equipo, agenda y finanzas. No hay selector de clínicas. Se conserva la identificación interna para una posible ampliación futura.

El **área principal** define los tipos de atención al registrar la clínica. En **Especialidades**, habilite solo **Odontología**, solo **Medicina** o las dos juntas (o ninguna, para otra área de la salud). Las mismas opciones aparecen en el formulario de la clínica del administrador del sistema. Cambiar después el área principal no modifica estas opciones ni sustituye los tipos de atención existentes.

Odontología habilita el odontograma y los dientes y caras de los elementos del presupuesto. Desactivarla conserva la consulta y la impresión de los elementos dentales existentes, pero impide crearlos, modificarlos o eliminarlos hasta habilitarla de nuevo. Los elementos generales siguen disponibles. Medicina prepara la configuración para extensiones médicas; la historia clínica común sigue disponible en cualquier área, según los permisos profesionales existentes. Habilitar un módulo no concede acceso a la historia clínica ni crea automáticamente formularios de especialidad.

En **Módulos** están las partes comunes a las especialidades: **Agenda**, **Historia clínica**, **Presupuestos**, **Financiero**, **Recordatorios**, **Cumpleaños**, [**Convenios**](convenios.md) y [**Personal**](pessoal.md). Una clínica nueva empieza con todos activos, y una instalación actualizada también. Un módulo desactivado sale del menú, de la pantalla de inicio y de la ficha del paciente para todo el equipo, incluido el administrador del sistema, y su dirección se rechaza. No se borra nada de lo ya registrado: al reactivarlo todo vuelve a aparecer. **Presupuestos** y **Personal** necesitan **Financiero** activo, porque aprobar un presupuesto crea la cuenta por cobrar y los sueldos del mes crean las cuentas por pagar. Pacientes, profesionales, equipo, tablas base, configuración y auditoría están siempre activos.

Si alguna cita futura quedara fuera del nuevo horario o del nuevo intervalo, el cambio se rechaza y la pantalla muestra cuál. Ajuste esa cita antes.

**Exigir verificación en dos pasos a quien accede a la historia clínica o al financiero** (viene activada): los profesionales con historia clínica, los administradores y el financiero solo usan el sistema después de activar el código de la aplicación autenticadora (vea [Primeros pasos](inicio.md)); hasta entonces, cada página lleva al código QR. La recepción no está obligada, y los ingresos públicos de la demostración nunca lo están.

## Tipos de atención
En **Registros > Tipos de atención**: los tipos (cirugía, consulta inicial…) y el color que cada uno pinta en la agenda. Para dejar de usar un tipo sin perder el historial, desmarque **activo**.

## Auditoría
En **Registros > Auditoría**: quién creó, modificó, eliminó o abrió cada registro de la clínica, cuándo, desde qué dirección y qué cambió. Los filtros buscan por usuario, acción, tipo de registro y período. Los registros no se pueden modificar. Los intentos de acceso rechazados se eliminan después de 30 días.

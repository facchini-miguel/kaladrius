---
sidebar_position: 8
---

# Configuración de la clínica

Estas pantallas son del **administrador de la clínica**, en el menú **Registros**.

## Configuración de la clínica
En **Registros > Configuración de la clínica**: nombre, documento (CPF/CNPJ en Brasil), correo electrónico y teléfono de la clínica, y el **horario de la agenda** (inicio, fin y duración de cada horario).

La instalación atiende a **una sola clínica**, con un registro de pacientes, equipo, agenda y finanzas. No hay selector de clínicas. Se conserva la identificación interna para una posible ampliación futura.

El **área principal** define los tipos de atención al registrar la clínica. En **Especialidades**, habilite solo **Odontología**, solo **Medicina** o las dos juntas (o ninguna, para otra área de la salud). Las mismas opciones aparecen en el formulario de la clínica del administrador del sistema. Cambiar después el área principal no modifica estas opciones ni sustituye los tipos de atención existentes.

Odontología habilita el odontograma y los dientes y caras de los elementos del presupuesto. Desactivarla conserva la consulta y la impresión de los elementos dentales existentes, pero impide crearlos, modificarlos o eliminarlos hasta habilitarla de nuevo (el administrador del sistema todavía puede, con un aviso). Los elementos generales siguen disponibles. Medicina prepara la configuración para extensiones médicas; la historia clínica común sigue disponible en cualquier área, según los permisos profesionales existentes. Habilitar un módulo no concede acceso a la historia clínica ni crea automáticamente formularios de especialidad.

En **Módulos** están las partes comunes a las especialidades: **Agenda**, **Historia clínica**, **Presupuestos**, **Financiero**, **Recordatorios**, **Cumpleaños**, [**Convenios**](health-plans.md) y [**Personal**](staff.md). Una clínica nueva empieza con todos activos, y una instalación actualizada también. Un módulo desactivado sale del menú, de la pantalla de inicio y de la ficha del paciente para todo el equipo, y su dirección se rechaza. El **administrador del sistema** sigue viéndolo, marcado como **desactivado** en el menú y con un aviso en sus pantallas, para mantenimiento o para conocerlo antes de activarlo. No se borra nada de lo ya registrado: al reactivarlo todo vuelve a aparecer. **Presupuestos** y **Personal** necesitan **Financiero** activo, porque aprobar un presupuesto crea la cuenta por cobrar y los sueldos del mes crean las cuentas por pagar. Pacientes, profesionales, equipo, tablas base, configuración y auditoría están siempre activos.

Si alguna cita futura quedara fuera del nuevo horario o del nuevo intervalo, el cambio se rechaza y la pantalla muestra cuál. Ajuste esa cita antes.

**Exigir verificación en dos pasos a quien accede a la historia clínica o al financiero** (viene activada): los profesionales con historia clínica, los administradores y el financiero solo usan el sistema después de activar el código de la aplicación autenticadora (vea [Primeros pasos](getting-started.md)); hasta entonces, cada página lleva al código QR. La recepción no está obligada, y los ingresos públicos de la demostración nunca lo están.

**País y zona horaria**: Brasil por defecto; también Estados Unidos, Reino Unido, Canadá, Australia y Sudáfrica, y en América Latina México, Argentina, Chile, Colombia, Perú, Uruguay, Paraguay, Bolivia y Ecuador. El país define las zonas horarias ofrecidas (la agenda y todos los horarios siguen la de la clínica, dondequiera que esté cada persona), los teléfonos en el formato del país con el código correcto de WhatsApp, los códigos postales (ZIP code, postcode…), el orden de las fechas en inglés (10/31 en Estados Unidos, 31/10 en Reino Unido, Australia y Sudáfrica, 2026-10-31 en Canadá) los números y las fechas en español (1,234.56 en México y Perú, 1.234,56 en los demás países latinoamericanos) y la moneda sugerida, que acompaña el cambio de país si no se eligió otra. Fuera de Brasil, el estado y la ciudad del paciente se escriben, y RG e inscripción estatal no aparecen.

**Numeración de los dientes**: cómo aparecen los dientes en el odontograma y en los presupuestos: **FDI** (11 a 48, dientes de leche 51 a 85), **Universal** (1 a 32 y A a T, usada en Estados Unidos) o **Palmer** (UR6, LL3, común en el Reino Unido). Empieza con la del país (Universal en Estados Unidos, FDI en los demás) y acompaña el cambio de país si no se eligió otra. Solo cambia la visualización: los dientes ya registrados siguen siendo los mismos.

**Documentos de cada país**: pacientes, clínica, proveedores y empleados reciben los documentos del país de la clínica, verificados por sus dígitos de control y escritos a la manera del país (12-3456789, 943 476 5919, 20-12345678-6), y cada uno mantiene su nombre oficial en todos los idiomas. En las fichas de paciente y de proveedor, el campo cambia al elegir persona física o jurídica; cuando un tipo no tiene documento, el campo desaparece. La clínica acepta el documento de persona física o de empresa. El registro profesional sigue libre, con los ejemplos del país (CRO, CRM… en Brasil; GDC, GMC… en el Reino Unido; NPI en Estados Unidos; cédula profesional en México).

| País | Paciente persona física | Empresa (paciente, proveedor, clínica) | Proveedor o clínica persona física | Empleado |
|---|---|---|---|---|
| Brasil | CPF | CNPJ | CPF | CPF |
| México | CURP | RFC | RFC | CURP |
| Argentina | DNI | CUIT | CUIT | DNI |
| Chile | RUT | RUT | RUT | RUT |
| Colombia | Cédula de ciudadanía | NIT | NIT | Cédula de ciudadanía |
| Perú | DNI | RUC | RUC | DNI |
| Uruguay | Cédula de identidad | RUT | RUT | Cédula de identidad |
| Paraguay | Cédula de identidad | RUC | RUC | Cédula de identidad |
| Bolivia | Cédula de identidad | NIT | NIT | Cédula de identidad |
| Ecuador | Cédula | RUC | RUC | Cédula |
| Estados Unidos | — | EIN | EIN | SSN |
| Reino Unido | NHS number | Company number | — | National Insurance number |
| Canadá | Health card number | Business Number | Business Number | SIN |
| Australia | Medicare number | ABN | ABN | — |
| Sudáfrica | ID number | Company registration number | — | ID number |

En Estados Unidos no se pide número nacional al paciente, y en Australia el tax file number de los empleados no se guarda (la ley restringe quién puede guardarlo). Si el país cambia, los documentos ya guardados quedan como están y se verifican de nuevo al editar.

**Moneda**: la moneda con que trabaja la clínica (real brasileño por defecto; también dólar estadounidense, euro, libra esterlina y los pesos argentino, mexicano, chileno, colombiano y uruguayo, el guaraní paraguayo, el sol peruano y el boliviano). Todos los valores del sistema, recibos incluidos, se muestran en ella, para todo el equipo y en el idioma que use cada uno: el idioma solo define los separadores (1.234,56 o 1,234.56). Cambiar la moneda **no convierte** los valores ya registrados; solo cambia cómo se muestran.

## Tipos de atención
En **Registros > Tipos de atención**: los tipos (cirugía, consulta inicial…) y el color que cada uno pinta en la agenda. Para dejar de usar un tipo sin perder el historial, desmarque **activo**. Los tipos predeterminados (Cirugía, Primera consulta…) aparecen en el idioma de cada persona; un tipo que la clínica crea o renombra aparece como se escribió.

## Auditoría
En **Registros > Auditoría**: quién creó, modificó, eliminó o abrió cada registro de la clínica, cuándo, desde qué dirección y qué cambió. Los filtros buscan por usuario, acción, tipo de registro y período. Los registros no se pueden modificar. Los intentos de acceso rechazados se eliminan después de 30 días.

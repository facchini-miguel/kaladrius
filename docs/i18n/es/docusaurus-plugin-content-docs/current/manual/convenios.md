---
sidebar_position: 3.7
---

# Convenios

El módulo **Convenios** guarda los convenios (planes de salud) que la clínica acepta y la credencial de cada paciente. Puede desactivarse en la [configuración de la clínica](clinica.md) si la clínica solo atiende pacientes particulares.

## Registrar un convenio
En **Registros > Convenios**, haga clic en **Nuevo convenio** y complete el nombre y, si lo hay, el **registro de la aseguradora** en el país de la clínica (en Brasil, la ANS, de 6 dígitos; en Estados Unidos, el Payer ID; en Argentina, el RNOS; en Sudáfrica, el número en el CMS), el teléfono y observaciones. En los países sin registro de aseguradoras el campo no aparece. El mismo nombre no puede registrarse dos veces. Para dejar de aceptar un convenio sin perder el historial, edítelo y desmarque **activo**: sale de la lista de credenciales nuevas, y las existentes se mantienen.

## La credencial del paciente
En la ficha del paciente, la tarjeta **Convenios** lista sus credenciales. Haga clic en **Nueva credencial** y elija el convenio, el **plan** (p. ej. "Básico"), el **número de la credencial**, la **validez** y, para un dependiente, el **titular** del plan. El mismo número de credencial no puede ser de dos pacientes del mismo convenio.

El número de la credencial lleva su nombre local (Member ID en Estados Unidos, membership number en el Reino Unido, Australia y Sudáfrica, número de afiliado en Argentina…). Las credenciales norteamericanas tienen también el **número de grupo**, y las familiares de Sudáfrica y Australia el **código del beneficiario** (dependant code, número del paciente en la tarjeta).

Una credencial con la validez pasada aparece como **Vencida**. Un paciente sin credencial aparece como **Particular**. Una credencial que ya no se usa puede marcarse como inactiva, sin borrarse.

## Quién hace qué
La recepción y el administrador registran convenios y credenciales; los profesionales y el perfil Financiero los consultan. Cuando los datos de un paciente se eliminan a pedido suyo (LGPD), sus credenciales también se borran.

Las guías, autorizaciones y la facturación a los convenios todavía no forman parte del sistema.

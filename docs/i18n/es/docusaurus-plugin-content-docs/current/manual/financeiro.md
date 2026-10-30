---
sidebar_position: 6
---

# Financiero

El menú **Financiero** muestra quién le debe a la clínica y cómo pagó cada persona. Los pagos ocurren fuera del sistema (efectivo, Pix, terminal de tarjetas) y se **registran** aquí. Lo usan la recepción y el administrador; el profesional no ve el financiero.

## Registrar un valor por cobrar
1. En **Financiero > Nueva cuenta** (o en el cuadro **Financiero** de la ficha del paciente), elija el **paciente**. Si quien paga no es un paciente registrado, escriba el nombre en **pagador**.
2. Indique la **descripción** (por ejemplo, "Tratamiento de conducto"), la **categoría**, el **profesional** (opcional) y el **valor total**.
3. En **Número de cuotas**, indique cuántas veces el paciente le pagará **a la clínica**, una por mes, a partir del **vencimiento de la 1.ª cuota**. Las cuotas tienen el mismo valor; los centavos que sobran van a la primera.
4. Si el paciente pagó en el momento, marque **La 1.ª cuota ya se pagó ahora**, elija la forma y la cuenta, y guarde: el recibo se abre a continuación.

**Las cuotas con tarjeta no son cuotas con la clínica.** Si el paciente pagó con tarjeta en 6 cuotas, a la clínica le paga la emisora: registre **1 cuota** y, al cobrar, indique las 6 cuotas en el campo **cuotas con tarjeta**. El paciente no debe nada.

## Cobrar
En **Financiero > Por cobrar**, la lista muestra las cuotas abiertas (las vencidas en rojo). Haga clic en **Cobrar** e indique:
- **valor cobrado** (puede ser solo una parte: el resto sigue abierto);
- **intereses y multa**, si se cobran, ya incluidos en el valor cobrado (el cálculo es manual);
- **forma de pago** y **cuenta** (Caja, Banco…);
- para tarjeta: marca, número de cuotas con tarjeta y código de la transacción. **Nunca** anote el número de la tarjeta.

Solo el administrador de la clínica puede dar **descuento**.

## Recibo
Después de cobrar, el recibo se abre listo para **imprimir o guardar como PDF**. Muestra los datos de la clínica (nombre, CPF/CNPJ, dirección y teléfono, de **Registros > Configuración de la clínica**), quién pagó, el valor, la cuota y la forma de pago. Para reimprimirlo, abra la cuenta y haga clic en **recibo** junto al pago.

## Deudores
En **Financiero > Deudores**, cada paciente con cuotas vencidas, el total vencido separado por tiempo de atraso (hasta 30, 31 a 60, 61 a 90 y más de 90 días), lo que todavía va a vencer y el vencimiento más antiguo. Haga clic en el nombre para abrir la ficha.

## Corregir un error
No se borra nada. El **administrador** puede:
- **revertir** un pago registrado por error (abra la cuenta y haga clic en **revertir**, indicando el motivo): la cuota vuelve a quedar abierta y el recibo pasa a mostrar "REVERTIDO";
- **cancelar** una cuenta (después de revertir sus pagos), indicando el motivo.

Todo queda registrado en la auditoría.

## Caja del día
En **Financiero > Caja del día**, la recepción controla el dinero de la caja:
1. **Abrir caja:** cuente el dinero e indique el valor. El sistema muestra cuánto debería tener la cuenta, solo como referencia.
2. Durante el día, los pagos registrados en la cuenta **Caixa** (caja) entran automáticamente.
3. **Retiro:** dinero que sale de la caja, con el motivo. Si se deposita en el banco, elija la cuenta **Banco** en **Otra cuenta**; vacío, el dinero sale del sistema (por ejemplo, un retiro del dueño).
4. **Refuerzo:** dinero que entra en la caja, como cambio.
5. **Cerrar caja:** cuente de nuevo e indique el valor. El sistema muestra cuánto debería haber y registra la **diferencia**; explíquela en la observación, si la hay.

Solo puede haber una caja abierta por cuenta. Las cajas cerradas quedan en **Cajas anteriores**, con lo esperado, lo contado y la diferencia.

## Cuentas por pagar (administrador)
En **Financiero > Nuevo gasto**, elija el **proveedor** registrado (en un pago suelto, escriba el nombre en **Proveedor sin registro**), la categoría, la descripción y el valor. En **El valor es**, elija:
- **el total, dividido en las cuotas**: una compra de R$ 900 en 3 cuotas pasa a 3 cuotas de R$ 300;
- **de cada mes**: una cuenta fija, como el alquiler de R$ 3.000 durante 12 meses, pasa a 12 cuotas de R$ 3.000.

En **Financiero > Por pagar**, haga clic en **Pagar** cuando pague una cuota. Revertir y cancelar funcionan igual que en las cuentas por cobrar.

## Flujo de caja (administrador)
En **Financiero > Flujo de caja**, elija el período y si quiere verlo por **día** o por **mes**:
- **Ingresos** y **Egresos**: lo que se cobró y se pagó de verdad, por la fecha del pago;
- **Ingresos previstos** y **Egresos previstos**: lo que falta de las cuotas abiertas, por el vencimiento (las vencidas aparecen como "atrasado");
- **Saldo**: empieza en el saldo de las cuentas al inicio del período y suma todo, día a día (o mes a mes).

Abajo aparece el **saldo actual de cada cuenta**. Para que coincida con el banco y la caja, indique el **saldo inicial** de cada cuenta en **Registros > Cuentas** (cuánto había antes del primer registro en el sistema).

## Informes (administrador)
En **Financiero > Informes**, para el período elegido: total cobrado, total pagado y el resultado; cobrado por forma de pago, por categoría y por profesional; y gastos pagados por categoría; con centros de costo registrados, también lo cobrado y lo pagado por **centro de costo**, con una línea "Sin centro de costo". Los pagos revertidos y las cuentas canceladas quedan fuera.

## Extracto bancario (administrador)
En **Financiero > Extracto bancario**, importe el extracto de la cuenta, descargado del sitio o la aplicación del banco en formato **OFX** (a veces llamado "Money"). Elija la cuenta del sistema (por ejemplo, Banco) y el archivo. Las transacciones ya importadas se omiten, así que puede importar períodos que se superponen. Si alguna línea del archivo no tiene fecha o importe legible, el sistema avisa cuántas quedaron fuera: revíselas en el extracto del banco.

Cada transacción del banco se compara con lo que el sistema ya tiene en esa cuenta: un cobro o pago **con el mismo valor, hasta 10 días antes o después**, o un depósito o retiro de la **caja del día** hacia esa cuenta.
- **Conciliar … con correspondencia única** concilia de una vez todas las transacciones que tienen un solo registro posible.
- Cuando hay más de uno posible, elíjalo en la lista y haga clic en **Conciliar**.
- Sin nada en el sistema (tasa, rendimiento, Pix que nadie registró), haga clic en **Crear registro**: el sistema crea el ingreso o el gasto ya pagado en esa fecha y cuenta, y lo concilia.
- Lo que no debe convertirse en registro (liquidación del terminal de tarjetas, transferencia entre cuentas de la clínica) puede **ignorarse** con un motivo.
- **deshacer** vuelve la transacción a pendiente. Si un pago conciliado se revierte, la transacción vuelve a quedar pendiente.

Arriba, el **saldo en el banco** informado en el archivo se compara con el **saldo en el sistema** en la misma fecha; con todo registrado, la diferencia queda en cero.

## Comisiones (administrador)
En **Financiero > Comisiones**, cada profesional tiene un **porcentaje** sobre el valor cobrado de las cuentas por cobrar en que aparece (el presupuesto aprobado ya lleva el profesional; en un registro nuevo, elija el profesional). Los registros sin profesional no generan comisión. La base es el dinero que entró, ya con descuentos y con intereses, si los hubo.

1. Haga clic en **Porcentaje** para definir el de cada profesional.
2. Elija la fecha en **Cobros hasta** (por ejemplo, el último día del mes) y haga clic en **Ver**: la tabla muestra lo cobrado aún no comisionado y la comisión por pagar.
3. Haga clic en **Pagar**, revise los cobros y el vencimiento y haga clic en **Registrar en Por pagar**. La comisión pasa a ser un gasto en **Por pagar**, a nombre del profesional, donde usted registra el pago.

Cada cobro entra en una comisión una sola vez. Si un cobro ya comisionado se **revierte**, su comisión se descuenta en el próximo pago al profesional (con el porcentaje de la época). Si el gasto de la comisión se **cancela**, la comisión se deshace y los cobros vuelven a quedar pendientes. Si una comisión posterior ya descontó el reverso de uno de sus cobros, cancele primero la posterior. El **Extracto** de cada comisión lista los cobros y los descuentos y puede imprimirse para el profesional.

## Proveedores
En **Registros > Proveedores**, registre a quién la clínica compra o paga: persona física o jurídica, nombre, razón social, CPF/CNPJ, teléfono, WhatsApp, correo electrónico y observaciones. El sistema verifica el CPF o CNPJ y no permite registrar dos veces el mismo documento. La ficha del proveedor muestra cuánto está **pendiente** y todas sus cuentas por pagar, y tiene el botón **Nuevo gasto**, que ya viene con él elegido. En las listas, el nombre del proveedor lleva a su ficha. Para dejar de usar un proveedor sin perder el historial, desmarque **activo**: sale del formulario de nuevo gasto, y las cuentas antiguas siguen vinculadas a él.

## Planificación (administrador)
En **Financiero > Planificación**, elija el año y complete la **meta del año** de cada grupo del [plan de cuentas](#plan-de-cuentas): cuánto quiere cobrar la clínica en atenciones, cuánto piensa gastar en personal, etc. La pantalla compara cada meta con lo **realizado** (cobrado y pagado en el año, por la fecha del pago, sumando los subgrupos), muestra el **%** y lo **esperado hasta hoy**, que es la meta proporcional a los días del año ya transcurridos. La insignia queda verde cuando el ingreso ya llegó a lo esperado o cuando el gasto aún está por debajo. **Copiar las metas** del año anterior solo completa los grupos aún sin meta. Valores sin separador de miles, como en los demás campos.

## Cierre (administrador)
Después de revisar la caja y entregar los informes al contador, cierre el período en **Financiero > Cierre**: elija **Cerrar hasta** (como máximo ayer). A partir de ahí, los pagos y reversiones con fecha en ese período o antes se rechazan, y los informes de ese período ya no cambian. Lo que ocurre hoy (cobrar, pagar, la caja del día) sigue normal. Para corregir un error, **Reabrir** lleva el cierre a una fecha anterior (o reabre todo) y pide el motivo, que queda en el historial de la pantalla y en la auditoría. El perfil Financiero también cierra y reabre; las cuentas públicas de demostración solo consultan.

## Centros de costo
El centro de costo indica **para quién** es cada ingreso o gasto: un consultorio, una especialidad, la administración. La categoría sigue indicando **qué** es (alquiler, material). En **Registros > Centros de costo**, el administrador registra los centros. En cuanto haya uno activo, el campo **Centro de costo** aparece en el nuevo registro y en el nuevo gasto (es opcional), y los informes muestran los cuadros por centro de costo. Los registros antiguos quedan sin centro. Para dejar de usar un centro sin perder el historial, desmarque **activo**.

## Plan de cuentas
En **Registros > Plan de cuentas**, las categorías se organizan en **grupos**, que pueden tener **subgrupos** (como en el plan de cuentas del contador). Cada grupo puede tener un **código** (1, 2, 3…), y los subgrupos forman números como **2.1**. Los registros siguen yendo en las categorías; los informes muestran lo cobrado y lo pagado **por grupo**, cada uno sumando los de abajo, y una línea "Sin grupo". Las clínicas nuevas empiezan con un plan básico, con los nombres guardados en portugués como las categorías predeterminadas ("Atendimentos" y "Outras receitas"; "Ocupação", "Pessoal", "Materiais e laboratório", "Impostos" y "Outras despesas"), que pueden renombrarse; en las clínicas que ya existían, las categorías con el nombre predeterminado entran en él y las demás quedan sin grupo hasta que alguien elija uno. Para cambiar una categoría de grupo, edite la categoría. Un grupo no puede quedar dentro de sí mismo ni mezclar ingresos con gastos.

## Categorías y cuentas
En **Registros > Categorías** y **Registros > Cuentas**, el administrador crea nuevas categorías (ingresos y gastos) y cuentas (caja, banco, terminal de tarjetas). Para dejar de usar una sin perder el historial, desmarque **activa**.

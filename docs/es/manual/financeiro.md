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

## Categorías y cuentas
En **Registros > Categorías** y **Registros > Cuentas**, el administrador crea nuevas categorías (ingresos y gastos) y cuentas (caja, banco, terminal de tarjetas). Para dejar de usar una sin perder el historial, desmarque **activa**.

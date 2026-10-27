# Plan del módulo financiero

[🇺🇸 English](../en/financial-plan.md) | [🇧🇷 Português](../pt-BR/plano-financeiro.md) | 🇪🇸 Español

> Estado: **etapa 1 (por cobrar) concluida en la 0.15.0** (27/10/2026). Decisiones 048 y 051. Los intereses y la multa se registran a mano, el descuento solo lo da el administrador, y la dirección de la clínica sale en el recibo.

## Objetivo
Saber **quién debe qué**, **cómo pagó cada persona** (efectivo, Pix, tarjeta, en cuotas) y **cuánto entra y sale** de la clínica, con registros hechos a mano por el equipo.

## Fuera del alcance (por decisión del titular)
- Emisión de factura (NFS-e) y del recibo de Receita Saúde.
- Integración con Pix, boleto, enlace de pago o terminal de tarjetas: el pago ocurre fuera del sistema y se **registra** en él.
- Convenios odontológicos.

Todo esto puede venir después; el modelo de abajo no lo impide.

## Conceptos

| Concepto | Qué es | Ejemplo |
|---|---|---|
| **Cuenta por cobrar** | Un valor que alguien le debe a la clínica, dividido en una o más cuotas | Tratamiento de conducto de R$ 1.200 en 3 cuotas |
| **Cuenta por pagar** | Un valor que la clínica debe | Alquiler de R$ 3.000, todos los días 10 |
| **Cuota** | Valor y vencimiento. Situación calculada: abierta, parcial, pagada, vencida, cancelada | 2.ª cuota, R$ 400, vence el 10/12 |
| **Pago** | Cuánto se pagó de una cuota, cuándo, cómo y a qué cuenta. Una cuota puede tener varios (pago parcial) | R$ 400 por Pix el 08/12 |
| **Cuenta** | Dónde está el dinero | Caja (efectivo), Banco, Terminal de tarjetas |
| **Categoría** | Para agrupar en los informes | Ingresos: Tratamiento, Consulta. Gastos: Alquiler, Material, Laboratorio, Salarios |

### Formas de pago
Efectivo, Pix, tarjeta de débito, tarjeta de crédito (en un pago o en cuotas en el terminal, con el número de cuotas), transferencia, boleto (pagado fuera del sistema) y cheque. En la tarjeta se guardan solo la marca y el código de la transacción (NSU), **nunca** el número de la tarjeta.

### En cuotas con tarjeta × en cuotas con la clínica
- **Con tarjeta:** el paciente paga todo de una vez (la emisora le divide el pago). La cuota del sistema queda **pagada**; el paciente no debe nada.
- **Con la clínica (crédito propio, talonario, cheques):** la cuenta por cobrar se crea con varias cuotas y vencimientos. El paciente **debe** cada cuota hasta pagarla. Es lo que aparece en "quién debe".

## Pantallas

| Pantalla | Contenido |
|---|---|
| **Financiero > Por cobrar** | Cuotas abiertas, filtros (vencidas, por vencer, período, paciente), botón **Cobrar** |
| **Nueva cuenta por cobrar** | Paciente (opcional; o el nombre de quien paga), descripción, categoría, profesional (opcional), valor total, número de cuotas, primer vencimiento e intervalo (mensual). Las cuotas pueden ajustarse antes de guardar. Opción "ya cobrado ahora" para el caso común de pago en el momento |
| **Cobrar** | Valor (la cuota entera o una parte), fecha, forma, cuenta, datos de la tarjeta. Genera el recibo |
| **Recibo** | Página lista para imprimir o guardar como PDF desde el navegador |
| **Financiero > Deudores** | Por paciente: total vencido y desde hace cuánto (hasta 30, 31–60, 61–90 y más de 90 días), con enlace a la ficha |
| **Ficha del paciente** | Cuadro "Financiero": saldo deudor, cuotas abiertas y últimos pagos |
| **Financiero > Por pagar** | Igual que "Por cobrar", con proveedor en lugar de paciente y repetición mensual (crea las próximas cuotas) |
| **Financiero > Flujo de caja** | Por día o mes: ingresos y egresos **realizados** (pagos) y **previstos** (cuotas abiertas), y saldo por cuenta |
| **Financiero > Caja del día** | Ingresos y egresos del día por cuenta, retiros y refuerzos, cierre con el valor contado y la diferencia |
| **Financiero > Informes** | Cobrado por forma de pago, por categoría y por profesional; gastos por categoría |
| **Registros > Financiero** | Cuentas y categorías (cada clínica empieza con una lista estándar) |

## Reglas
- No se borra nada de verdad: una cuenta pasa a **cancelada** y un pago a **revertido**, con motivo. Todo queda en la auditoría.
- La suma de las cuotas es igual al valor total; un pago no supera lo que falta de la cuota.
- Valores en reales con centavos (`Decimal`, nunca coma flotante).
- Aislamiento por clínica, como el resto del sistema.

## Permisos
Dos módulos nuevos en la matriz:

| Módulo | Admin | Recepción | Profesional |
|---|---|---|---|
| **Cobros** (por cobrar, cobrar, recibo, deudores, caja del día) | todo | ver, crear, modificar | — |
| **Financiero** (por pagar, flujo de caja, informes, cuentas y categorías) | todo | — | — |

Cancelar cuentas y revertir pagos es solo del administrador. Así la recepción cobra y consulta quién debe, pero no ve los salarios y gastos de la clínica.

## Etapas

| # | Etapa | Entrega | Versión |
|---|---|---|---|
| 1 ✅ | **Por cobrar** | Modelos, cuentas y categorías estándar, cuenta por cobrar con cuotas, cobrar (todas las formas, parcial), recibo, deudores, cuadro en la ficha del paciente, permisos | 0.15.0 |
| 2 | **Por pagar y flujo de caja** | Cuenta por pagar con repetición mensual, flujo de caja realizado y previsto, saldo por cuenta, informes | 0.16.0 |
| 3 | **Caja del día** | Apertura, retiros, refuerzos y cierre con conteo | 0.17.0 |

### Después (sin fecha)
Tabla de procedimientos y **presupuesto** que se vuelve cuenta por cobrar; **comisión de los profesionales**; resultado del período; tasas y fechas de acreditación del terminal de tarjetas; importación del extracto bancario (OFX). Y, si se decide: factura, Pix/boleto integrados, convenios.

## Supuestos adoptados (pueden revisarse)
1. El financiero viene **antes** de la fase 2 (API y app).
2. Presupuesto y comisión quedan para después de las 3 etapas.
3. Una cuenta por cobrar puede no tener un paciente registrado (nombre de quien paga como texto).
4. Una cuenta por cobrar puede indicar el profesional, para la futura comisión.
5. Todo el módulo nace en los tres idiomas de la interfaz.

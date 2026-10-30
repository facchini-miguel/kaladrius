---
sidebar_position: 6.5
---

# Personal

El módulo **Personal** guarda los empleados de la clínica, sus salarios y las horas extras y ausencias de cada mes, y convierte los sueldos del mes en cuentas por pagar en el [financiero](financeiro.md). Solo lo ven el administrador y el perfil Financiero. Puede desactivarse en la [configuración de la clínica](clinica.md) y necesita Financiero activo.

Las cargas sociales, vacaciones y aguinaldo **no** se calculan: quedan con el contador o con el sistema de sueldos.

## Empleados
En **Financiero > Empleados**, haga clic en **Nuevo empleado**: nombre, CPF, cargo, ingreso, teléfono y el **salario** (desde el ingreso, si no elige otra fecha). En un aumento, edite el empleado y complete **Nuevo salario** y la fecha desde la que vale: el salario anterior queda en el **historial de salarios**, y cada mes usa el salario vigente al final de él. Quien se fue recibe una **fecha de baja** y deja de aparecer en los meses siguientes.

## Los sueldos del mes
En **Financiero > Sueldos del mes**, elija el mes. Aparece una línea por empleado que trabajó en él, con el salario. Complete:
- **Horas extras**: la cantidad y el valor de la hora. El valor viene sugerido como salario ÷ 220 horas × 1,5 (el adicional mínimo para 44 horas semanales en Brasil) y puede cambiarse.
- **Ausencias**: los días de ausencia; cada uno descuenta salario ÷ 30.

El **total** es salario + horas extras − ausencias. **Guardar** conserva lo escrito. **Guardar y registrar en el financiero** convierte cada línea en una **cuenta por pagar** a nombre del empleado, en la categoría elegida (por defecto, "Salários e encargos") y con el vencimiento elegido. La línea registrada ya no cambia en esta pantalla; para rehacerla, cancele la cuenta en el financiero y la línea vuelve a quedar abierta.

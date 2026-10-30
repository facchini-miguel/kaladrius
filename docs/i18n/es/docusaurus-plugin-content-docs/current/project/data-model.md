---
sidebar_position: 3
---

# Modelo de datos

## Principio multiclínica
- Toda información de una clínica tiene una clave `clinica`. Ninguna consulta se hace sin filtrar por la clínica actual.
- El filtro se aplica de forma centralizada (middleware + managers), no a mano en cada pantalla.
- **Falla cerrada:** todo modelo de la clínica hereda de `ModeloDaClinica` (`apps/core/isolamento.py`). El manager por defecto filtra por la clínica actual y, si no hay clínica definida, **da error en lugar de mostrar datos**. El filtro se decide **cuando la consulta se ejecuta** (no cuando se arma), lo que permite declarar campos de formulario con datos de la clínica. Guardar o eliminar un registro de otra clínica también da error. El código de la plataforma que necesita ver todas las clínicas (admin de Django, comandos) usa `sem_isolamento()` de forma explícita.
- La clínica actual viene de la sesión y solo se acepta si el usuario tiene un vínculo activo con ella (o es superusuario). El admin de Django está restringido a los superusuarios de la plataforma.
- Las tablas de referencia públicas (estado, ciudad, banco, estado civil) son **globales**, compartidas entre las clínicas.

## Entidades

### Plataforma
| Entidad | Campos principales | Observación |
|---|---|---|
| `Clinica` | nombre, documento (CPF/CNPJ), contacto, activa, configuración de la agenda (inicio, fin, duración del horario) | El *tenant* |
| `Usuario` | usuario, nombre, correo, contraseña (Argon2), activo, idioma | Usuario de Django |
| `Vinculo` | usuario, clínica, perfil, activo | Un usuario puede trabajar en más de una clínica |

### Perfiles y permisos (reemplaza `sist_pessoasgrupos` / `sist_modulosperm`)
| Perfil | Equivalente en el sistema antiguo | Acceso por defecto |
|---|---|---|
| Superusuario de la plataforma | MASTER | Todo, en todas las clínicas |
| Administrador de la clínica | ADMINISTRADOR | Todo dentro de su clínica |
| Recepción | — | Agenda, pacientes, recordatorios, cumpleaños |
| Profesional | — | Agenda y pacientes. Ve y modifica **solo su propia agenda**: la del registro de profesional vinculado a su usuario en Registros > Profesionales (decisión 044). Sin registro vinculado, la agenda queda vacía, con un aviso |

Cada perfil recibe los permisos `ver`, `crear`, `modificar` y `eliminar` por módulo. La matriz está en `apps/core/permissoes.py` y vale tanto en el servidor (la solicitud se bloquea) como en la pantalla (botones y menús desaparecen).

| Módulo | Administrador | Recepción | Profesional |
|---|---|---|---|
| Pacientes | todo | ver, crear, modificar | ver, crear, modificar |
| Agenda | todo | todo | ver, crear, modificar |
| Recordatorios | todo | todo | ver, crear, modificar |
| Cumpleaños | todo | ver | ver |
| Profesionales | todo | ver | ver |
| Tablas base | todo | ver | ver |
| Usuarios de la clínica | todo | — | — |
| Configuración de la clínica | todo | — | — |
| Auditoría | ver | — | — |
| Cobros (por cobrar, cobrar, recibo, deudores) | todo | ver, crear, modificar | — |
| Financiero (categorías, cuentas; por pagar y flujo de caja en la 0.16) | todo | — | — |
| Presupuestos (aprobar exige también Cobros) | todo | ver, crear, modificar | ver, crear, modificar |

El módulo "Usuarios de la clínica" es la pantalla **Registros > Equipo** (versión 0.8.0): el administrador crea cuentas ya vinculadas a la clínica, cambia el perfil, define contraseñas y quita el acceso (el vínculo queda inactivo; las cuentas nunca se eliminan, por la auditoría). Nadie cambia su propio perfil, y la clínica nunca queda sin un administrador activo. El nombre, el correo y la contraseña solo pueden cambiarse cuando la cuenta se usa **solo** en esta clínica y no es de superusuario: así, una clínica no puede quitarle a alguien el acceso a las otras. "Configuración de la clínica" es la pantalla **Registros > Configuración de la clínica** (versión 0.10.0): nombre, CPF/CNPJ, correo, teléfono, horario e intervalo de la agenda. Un cambio de horario o intervalo que dejaría alguna cita **futura** fuera de la grilla o del intervalo se rechaza, y la pantalla muestra cuál (el historial puede tener otros horarios).

### Clínica
| Entidad | Campos principales | Sistema antiguo |
|---|---|---|
| `Paciente` | clínica, tipo (PF/PJ), nombre, razón social, CPF/CNPJ, RG, inscripción estatal, sexo, estado civil, nacimiento, profesión, responsable, teléfonos (casa, trabajo, celular), WhatsApp, correo, dirección (CEP, estado, ciudad, barrio, calle, número, complemento), observaciones, activo, archivado (con fecha y quién archivó), fechas de creación y modificación | `pessoas` |
| `Profissional` | clínica, nombre, registro profesional (CRO/CRM…), color, comisión (%, desde la 0.19), activo, usuario (opcional) | `dentistas` |
| `TipoAtendimento` | clínica, nombre, color, activo | `agenda_cor` (Cirugía, Prótesis…) |
| `Agendamento` | clínica, profesional, tipo, inicio y fin (fecha y hora), paciente (opcional), descripción, situación (agendada, asistió, faltó, canceló; desde la 0.24), serie (repetición), creado por | `agendax` |
| `Rechamada` | clínica, paciente, fecha, descripción, completado, creado por | `agenda` (is_rechamada) |

### Referencia (globales)
`UF`, `Cidade` (fuente: IBGE), `Banco` (fuente: lista pública del Banco Central de Brasil), `EstadoCivil`.

### Financiero (versión 0.15.0)
| Entidad | Campos principales | Observación |
|---|---|---|
| `Conta` (cuenta) | clínica, nombre, tipo (efectivo, banco, terminal de tarjetas), saldo inicial (0.16.0), activa | Dónde entra el dinero. Toda clínica empieza con Caixa (caja) y Banco |
| `Categoria` (categoría) | clínica, nombre, tipo (ingreso, gasto), activa | Toda clínica empieza con 3 de ingresos y 8 de gastos; el administrador registra otras |
| `Lancamento` (cuenta por cobrar o por pagar) | clínica, tipo (por cobrar, por pagar), descripción, categoría, paciente (opcional) o pagador como texto, profesional (opcional), valor total, fecha, observaciones, cancelado (con motivo, cuándo y quién), creado por | Nunca se elimina: se cancela |
| `Parcela` (cuota) | clínica, cuenta, número, vencimiento, valor | Lo pagado y el saldo se calculan a partir de los pagos |
| `Pagamento` (pago) | clínica, cuota, fecha, valor cobrado, intereses y multa (incluidos en el valor), descuento (solo administrador), forma (efectivo, Pix, débito, crédito, transferencia, boleto, cheque), cuenta, marca, cuotas y código de la transacción de la tarjeta, observación, revertido (con motivo, cuándo y quién), cobrado por | Se descuenta de la cuota: valor − intereses + descuento. Nunca guarda el número de la tarjeta |

| `Caixa` (caja) | clínica, cuenta, abierta el/por, valor contado en la apertura, cerrada el/por, valor esperado y contado en el cierre, observación | Caja del día (0.17.0). Una abierta por cuenta; lo esperado se guarda al cerrar, para que reversiones posteriores no cambien una caja cerrada |
| `MovimentoCaixa` (movimiento de caja) | clínica, caja, tipo (retiro, refuerzo), valor, otra cuenta (opcional), motivo, creado por | Un retiro a otra cuenta (depósito en el banco) mueve el saldo entre las cuentas; sin otra cuenta, el dinero sale o entra al sistema y aparece en el flujo de caja |
| `Comissao` (comisión) | clínica, profesional, cobros hasta, porcentaje, valor cobrado, comisión de reversiones descontada, valor, cuenta por pagar, cancelada, creado por | Desde la 0.19. Los pagos cubiertos apuntan a ella (`Pagamento.comissao`), y la reversión de uno de ellos, descontada después, apunta a la comisión que la descontó (`Pagamento.comissao_estorno`); así ningún cobro se comisiona dos veces. Cancelar la cuenta por pagar cancela la comisión y libera los pagos |
| `ImportacaoExtrato` (importación de extracto) | clínica, cuenta, archivo, código del banco, cuenta en el banco, inicio, fin, saldo en el banco y fecha, transacciones nuevas y ya importadas, importado por/el | Desde la 0.20. El archivo OFX no se guarda, solo las transacciones |
| `TransacaoBancaria` (transacción bancaria) | clínica, cuenta, importación, identificador en el banco (FITID), fecha, valor (positivo entra, negativo sale), descripción, tipo en el banco, situación (pendiente, conciliada, ignorada), pago o movimiento de caja (como máximo uno), motivo, conciliado por/el | Única por cuenta e identificador: reimportar no duplica. Un pago solo se concilia con una transacción; si se revierte, la transacción vuelve a pendiente |

Las cuentas por pagar (0.16.0) usan las mismas entidades. Desde la 0.37.0, la cuenta por pagar puede tener un `Fornecedor` registrado (persona física o jurídica, CPF/CNPJ único en la clínica, teléfono, WhatsApp, correo, activo), cuyo nombre también se copia en el campo del pagador; un pago suelto sigue aceptando el nombre escrito. Las categorías pueden pertenecer a un `GrupoContabil` (plan de cuentas: nombre, tipo, grupo superior y código opcionales, activo; decisión 097). El registro también puede tener un `CentroCusto` (centro de costo: nombre, activo; uno por registro, opcional, decisión 095). Los convenios (app `convenios`, 0.37.0) son `Convenio` (nombre, registro en la ANS, teléfono, activo) y la `Carteirinha` (credencial) del paciente (convenio, plan, número único en el convenio, validez, titular, activa). El saldo de cada cuenta es el saldo inicial más lo que entró menos lo que salió (pagos no revertidos). Valores en `Decimal` con 2 decimales. La cuota se bloquea en la base al cobrar, para que dos personas no paguen la misma cuota por encima del saldo. En la eliminación definitiva de un paciente, sus cuentas quedan (historial contable) con el pagador "Paciente excluído (código N)", y su auditoría pierde los datos personales.

### Presupuestos (versión 0.18.0)
| Entidad | Campos principales | Observación |
|---|---|---|
| `Procedimento` (procedimiento) | clínica, nombre, valor, categoría de ingreso, activo | Tabla de precios de la clínica |
| `Orcamento` (presupuesto) | clínica, paciente, profesional, fecha, validez, situación (abierto, aprobado, rechazado), descuento (solo administrador), observaciones, cuenta por cobrar, aprobado o rechazado el/por, creado por | Al aprobarse, pasa a ser un `Lancamento` por cobrar y ya no cambia |
| `ItemOrcamento` (ítem del presupuesto) | clínica, presupuesto, procedimiento (opcional), descripción, dientes (FDI, separados por coma), caras o región, cantidad, valor unitario | Descripción y valor copiados de la tabla en el momento; cambiar la tabla no modifica los presupuestos |

En la eliminación definitiva de un paciente, sus presupuestos se eliminan (los dientes son datos de salud) y su auditoría pierde los datos personales.

### Sistema
| Entidad | Uso |
|---|---|
| Versiones | Se leen del archivo `releases.yaml` (no están en la base de datos). Ver [versionado-y-versiones.md](versioning.md) |
| `RegistroAuditoria` | Quién creó, modificó o eliminó qué y cuándo (LGPD) |
| `Backup` | Cada copia de seguridad diaria enviada a Cloud Storage, registrada por el servidor. Si la última tiene más de 26 horas, los superusuarios ven un aviso en la parte superior de las pantallas |

## Agenda
- `Agendamento` guarda el inicio y el fin como fecha y hora con huso horario. Las citas de una misma repetición semanal comparten el campo `serie`.
- Reglas: horarios alineados con la duración configurada de la clínica y dentro del horario de atención; sin superposición para el mismo profesional (los horarios contiguos están permitidos).
- La superposición se verifica en el formulario (con un mensaje que dice con quién es el conflicto) **y** por una *exclusion constraint* de PostgreSQL (`btree_gist`), que vale incluso con dos personas guardando al mismo tiempo. Las citas **canceladas** (0.24) quedan fuera de ambas verificaciones: siguen en el historial, pero liberan el horario.

## Auditoría (LGPD)
- `RegistroAuditoria` (`apps/auditoria`) guarda **quién**, **cuándo**, **desde qué IP**, **qué acción** y, en los cambios, el **antes y después** de cada campo.
- Se registra automáticamente (señales de Django): crear, modificar y eliminar Paciente, Agendamento, Rechamada, Profissional, TipoAtendimento, Clínica, Vínculo y Usuario. También: abrir la ficha de un paciente, entrar, salir e intentos de acceso rechazados.
- **Nunca** guarda contraseñas ni su hash (el cambio de contraseña aparece solo como "cambiada").
- Los registros guardan los códigos de clínica y usuario sin clave foránea rígida: el historial sobrevive a la eliminación de un usuario o una clínica. No se pueden editar ni eliminar (admin de solo lectura), con una excepción: los intentos de acceso rechazados, que guardan el usuario escrito, se eliminan después de 30 días con el comando `aplicar_retencao`, que el servidor ejecuta todos los días junto con la copia de seguridad (decisión 045). En las copias, duran 30 días más. En la eliminación definitiva de un paciente, sus registros pierden los datos personales (ver abajo).
- El nombre del tipo de registro se guarda siempre en portugués, sea cual sea el idioma del usuario: los filtros y la anonimización dependen de él.
- Pantalla **Registros > Auditoría**, solo para el administrador de la clínica, filtrada por la clínica actual. Los cambios en cuentas de usuario (que no pertenecen a una clínica) quedan registrados en la clínica donde se hicieron. Los accesos al sistema no pertenecen a una clínica y aparecen solo para el superusuario, en el admin.

## Idioma del usuario
`Usuario.idioma` guarda el idioma elegido (`pt-br`, `en`, `es` o vacío para seguir al navegador). No entra en la auditoría, como la última versión vista.

## Ficha del paciente
Muestra identificación, contacto, observaciones, las próximas y las últimas 10 citas (versión 0.12.0; para el profesional, solo las de su propia agenda, con enlace a la semana en la agenda) y los recordatorios.

## Pacientes inactivos, archivados y eliminados (versión 0.9.0)
- **Inactivo:** dejó de venir, pero sigue visible para todo el equipo (filtro "Inactivos"). No aparece en los cumpleaños.
- **Archivado** (reemplaza el "eliminar" del día a día, decisión 046): el paciente sale de las listas, la búsqueda, la agenda (sugerencias), los cumpleaños y los recordatorios del equipo. No se borra nada: citas, recordatorios y auditoría se conservan, y las citas antiguas siguen mostrando el nombre. Solo el administrador de la clínica archiva, ve los archivados (lista de pacientes, Situación: Archivados) y restaura. El CPF/CNPJ de un archivado sigue reservado; la pantalla avisa que hay que pedir la restauración.
- **Eliminado definitivamente:** solo a partir de un paciente archivado, por el administrador, cuando el propio paciente pide la eliminación de sus datos (LGPD, art. 18). El registro y los recordatorios se eliminan, las citas quedan sin el paciente, y los registros de auditoría del paciente, de sus citas y recordatorios pierden los datos personales (`apps/auditoria/registro.py`, `anonimizar`): quedan quién, qué, cuándo, el código y los nombres de los campos. La pantalla recuerda que la clínica puede estar obligada a guardar la historia clínica (Ley 13.787/2018).

## Documentos y formatos
- CPF, CNPJ, teléfonos y CEP se guardan **sin puntuación** y se formatean solo al mostrarlos (filtros en `apps/core/templatetags/formatos.py`).
- El CNPJ acepta el **formato alfanumérico** de la Receita Federal (vigente desde julio de 2026: letras en las 12 primeras posiciones, dígitos verificadores numéricos). Validación en `apps/core/validadores.py`.
- El CPF/CNPJ es opcional (niños, por ejemplo), pero **único dentro de la clínica** cuando se informa.

## Diferencias intencionales con el sistema antiguo
| Antes | Ahora | Motivo |
|---|---|---|
| Dentista | Profesional | Sistema genérico |
| Colores fijos de la agenda | Tipos de atención configurables por clínica | Cada especialidad tiene los suyos |
| Cita solo con texto libre | Paciente **opcional** vinculado + descripción | Base para la app del paciente, sin perder el uso rápido |
| Tablas de barrio y calle mantenidas a mano | Dirección en campos de texto + estado y ciudad de la tabla del IBGE | Menos mantenimiento. La búsqueda por CEP viene después |
| Saldo, fecha de pago, banco, agencia y cuenta en el paciente | **Fuera de la fase 1** | Pertenecen al módulo financiero |
| MSN, página web, fax | Eliminados | Obsoletos |
| Fechas `0000-00-00` | Campos opcionales (NULL) | Integridad |
| Sin claves foráneas | Claves foráneas e índices | Integridad y rendimiento |

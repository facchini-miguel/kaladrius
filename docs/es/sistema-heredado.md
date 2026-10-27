# Sistema heredado (Odonto System)

[🇺🇸 English](../en/legacy-system.md) | [🇧🇷 Português](../pt-BR/sistema-legado.md) | 🇪🇸 Español

Referencia para la reescritura. El código antiguo (PHP) y las copias de seguridad están **fuera del repositorio**, en la carpeta local `~/medical-system-old_data/` (acceso solo del dueño). El análisis completo está en `~/medical-system-old_data/legado-php/ANALISE_SISTEMA.md`.

> Las copias de seguridad tienen datos reales de pacientes (LGPD). **Nunca** copiar nada de allí al repositorio, a imágenes Docker ni a las pruebas, que usan solo **datos ficticios**. Por seguridad, `old_data/` sigue en `.gitignore` y en `.dockerignore`.

## Resumen
- PHP 5.3 sin framework, MySQL 5.5 (MyISAM, latin1), jQuery 1.x. Escrito en 2009–2010, usado hasta nov/2019.
- ~20 mil líneas, ~110 páginas, 17 tablas.
- No funciona en PHP actual (`mysql_*` se eliminó en PHP 7).

## Funciones a reproducir (paridad)
| Módulo | Comportamiento a mantener |
|---|---|
| Acceso | Usuario + contraseña. El usuario inactivo no entra. Pantalla inicial con usuario y grupo |
| Permisos | Por grupo y opción de menú: consultar, registrar, modificar, eliminar. Los botones aparecen según el permiso |
| Personas | PF/PJ, dirección encadenada (estado → ciudad → barrio → calle), 4 teléfonos, observaciones, activo. Lista paginada alfabética, búsqueda por nombre, ID y CPF/CNPJ. Ver, modificar, eliminar con confirmación. Edad calculada |
| Agenda | Semana lun–dom, 07:30–20:00, horarios de 30 min, por dentista (elegido en un select y recordado en la sesión). Navegación `<<`/`>>` e "ir a la fecha". Bloque coloreado por tipo. Leyenda de colores. Clic en un horario vacío abre el registro (dentista, tipo, inicio, fin, fecha, descripción). Repetición "ocurre N veces" (semanal). Horarios solo en :00/:30. El conflicto de horario del mismo dentista bloquea el guardado. Editar y eliminar en el bloque. Íconos de recordatorios y cumpleaños al pie de cada día |
| Recordatorios | Persona + fecha + descripción. Listar, registrar, modificar. Aparece en la agenda |
| Cumpleaños | Lista por mes (nombre + fecha) con enlace a la ficha |
| Dentistas | CRUD (nombre) |
| Tablas base | Estado, ciudad, barrio, calle, banco, tipo de dirección, estado civil |
| Sistema | CRUD de usuarios y grupos, regeneración de permisos estándar |

## Revisión de paridad (26/10/2026)
Los 185 archivos PHP se compararon con el sistema nuevo.
- **Reproducido:** todo lo de la tabla de arriba, incluida la gestión de usuarios, que llegó en la versión 0.8.0 (pantalla Equipo, con perfiles fijos en lugar de grupos configurables; decisión 040). Barrio, calle y tipo de dirección pasaron a ser campos de texto (ver [modelo-de-datos.md](modelo-de-datos.md)).
- **No había módulo financiero:** nada de caja, cuentas por cobrar ni presupuestos. Solo los campos saldo, fecha de pago y banco/agencia/cuenta en `pessoas`, más observaciones libres. Confirmado en todos los dumps (2011–2019, siempre las mismas 17 tablas) y en los archivos comprimidos (`www*.rar` tienen los mismos 185 archivos PHP). El financiero se hará desde cero (ver [plan-financiero.md](plan-financiero.md)).
- **No portado a propósito** (código muerto en el sistema antiguo): personas relacionadas (la página de destino nunca existió), `config_imp.php` (sin enlace en ninguna pantalla) y el campo `rg_obs`.

## Importación de los datos (versión 0.8.0)
El comando `importar_legado` (`apps/legado`) lee el dump de MySQL directamente (sin necesitar MySQL) y crea todo en una clínica nueva, de una vez: si algo falla, no queda nada guardado. Se niega a importar en una clínica que ya tenga pacientes.

```bash
docker compose exec -T app python manage.py importar_legado - --clinica "Nombre de la clínica" \
  < ~/medical-system-old_data/backup_20191106/facchini07_20191106.sql
```

| Sistema antiguo | Sistema nuevo |
|---|---|
| `dentistas` | Profesionales (sin el `_` que el sistema antiguo usaba al inicio del nombre para ordenar) |
| `agenda_cor` | Tipos de atención de la clínica, asociados por el nombre (sin acentos) |
| `pessoas` | Pacientes. La ciudad se asocia a la lista del IBGE por el nombre; barrio y calle pasan a texto; se recupera el cero a la izquierda perdido del CPF; se mantiene la fecha de registro |
| `agendax` | Citas, solo con la descripción, como en el sistema antiguo (sin paciente vinculado). Las que no tienen descripción (horarios bloqueados, como "Ocupado") reciben el nombre del tipo, porque la agenda exige paciente o descripción |
| `agenda` (recordatorios) | Recordatorios. Los de fechas pasadas entran como completados, porque el sistema antiguo no marcaba la conclusión |
| Usuarios y grupos | No importados: el equipo se registra en **Registros > Equipo** |

- Lo que no tiene un campo propio va a las **observaciones** del paciente, en un bloque "[Sistema antigo]": código antiguo, saldo, fecha del último pago, banco/agencia/cuenta, fax, sitio, MSN, además de documentos, correos, CEP y ciudades que no se pudieron usar (CPF/CNPJ no válido o repetido, por ejemplo). No se descarta nada.
- Los teléfonos sin código de área quedan como estaban: la clínica tenía pacientes con códigos 51 y 54, así que no se puede deducir.
- Las citas superpuestas o sin profesional no entran, y el fin antes del inicio pasa a 30 minutos. Si hay atenciones fuera del horario de la agenda, el horario de la clínica se amplía. El comando muestra un informe con la cantidad de cada caso, y la importación queda registrada en la auditoría de la clínica.

Resultado con el dump del 06/11/2019, en el entorno **local** (27/10/2026): 1.093 pacientes, 18.590 citas (2010–2020), 41 recordatorios y 2 profesionales. Quedaron fuera 1 cita sin profesional y 1 recordatorio de un paciente borrado; 37 CPF/CNPJ no válidos o repetidos fueron a las observaciones; la agenda pasó a ir hasta las 22:00. **Producción:** importado el 27/10/2026 en la "Clínica Sorriso", con el mismo resultado, después de eliminar los datos ficticios (`remover_dados_teste`). El mismo día, antes de la primera copia de seguridad con ellos, fueron **anonimizados** (ver abajo): la producción ya no guarda los datos reales. El procedimiento está en [despliegue.md](despliegue.md).

## Anonimización (versión 0.11.0)
Los datos importados son de una clínica que ya no es cliente. Por eso, el titular decidió usarlos solo como **datos de prueba**, anonimizados (decisión 047). El comando `anonimizar_clinica --clinica "Nombre" --confirmar` reemplaza, de forma aleatoria e irreversible (sin semilla y sin tabla de correspondencia; LGPD, art. 12):
- **pacientes:** nombre, razón social, CPF/CNPJ (nuevos, válidos y falsos), RG, inscripción estatal, profesión, responsable, teléfonos (se mantiene el código de área), correo (`@example.com`), CEP (mantiene los 2 primeros dígitos), barrio, calle, número, complemento y observaciones (frases genéricas). La fecha de nacimiento se desplaza hasta 180 días, para mantener las edades;
- **citas:** la descripción pasa a "nombre ficticio - tipo de atención". Los horarios bloqueados (descripción igual al tipo, como "Ocupado") quedan como están;
- **recordatorios:** la descripción pasa a un texto genérico ("Retorno", "Limpeza"…);
- **profesionales:** nombre y registro;
- **financiero** (desde la 0.15.0): la descripción de las cuentas pasa a ser el nombre de la categoría, el pagador como texto pasa a un nombre ficticio, y se borran las observaciones y los códigos de transacción;
- **auditoría:** se eliminan los registros de la clínica sobre esos datos, que guardaban los valores originales.

Se mantienen: las cantidades, las fechas y horarios de la agenda, el profesional de cada cita, los tipos de atención, las ciudades, PF/PJ, sexo, estado civil, situación (activo, archivado) y las fechas de registro. Verificado en el entorno local, cruzando con el dump original: no quedó ningún nombre completo, CPF/CNPJ, teléfono ni descripción de cita original.

### Movimiento simulado (versión 0.12.0)
La agenda importada termina en 2020, y los 41 recordatorios antiguos entraron como completados. Para que la clínica de prueba tenga movimiento actual, el comando `simular_movimento --clinica "Nombre" --confirmar` crea citas ficticias con pacientes, de 2 semanas atrás a 4 semanas adelante (cerca del 60 % de los horarios libres de los días hábiles), 80 recordatorios de 30 días atrás a 60 días adelante y, desde la 0.15.0, 60 cuentas por cobrar de los últimos 90 días (la mayoría de las cuotas vencidas pagadas, algunas atrasadas) y, desde la 0.16.0, gastos ficticios (alquiler, servicios y honorarios mensuales, material y laboratorio); `--lancamentos 0` para ninguno. Usa solo pacientes activos y no archivados, y salta los horarios ya ocupados. `--sem-agenda` crea solo los recordatorios. **Nunca** usarlo en una clínica real.

## Tipos de atención originales (datos de prueba)
Liberado `#b9f1a7` · Cirurgia `#f7a5a5` · Dentística `#f6f7a5` · Periodontia `#7b88cb` · Consulta Inicial `#e7a5f7` · Prótese `#fed27d` · Endodontia `#e96cd9` · Ortodontia `#a7eef1` · Atendimento de 15 em 15 `#d5dae6` · Ocupado `#a7bef1`

## Problemas que resuelve la reescritura
SQL injection generalizado (incluso en el acceso), scripts de guardado sin verificación de acceso, contraseñas MD5 sin sal, credenciales en el código, XSS, ausencia de CSRF, errores ocultos, código duplicado, ausencia de pruebas, diseño no adaptable a móviles.

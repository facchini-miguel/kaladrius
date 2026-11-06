---
sidebar_position: 3.5
---

# Glosario de nombres

Los nombres del código están pasando del portugués al inglés (decisiones 155 a 159); las pantallas siguen en portugués, con traducciones. Esta página es la lista que siguen las personas y la herramienta de renombrado: un nombre en inglés para cada nombre en portugués, en todo el código.

## Cómo se renombra un nombre

- **Solo cambian identificadores**, leídos como tokens de Python y variables de plantilla, nunca como texto: los textos de las pantallas, los `_()` y los `{% translate %}` quedan como están.
- **La base sigue al código** (decisión 179): una tabla se llama `<app>_<modelo>` (`patients_patient`), una columna como su campo (`birth_date`), un índice o restricción por lo que hace (`appointment_no_overlap`). Hasta la decisión 179 los renombrados mantenían las tablas y columnas en portugués (`Meta.db_table`, `db_column`), para que la versión anterior siguiera funcionando.
- **Un renombrado nunca choca**: un archivo que ya usa el nombre nuevo para otra cosa (una variable `date` junto a un campo `data`, el `type` de Python) se hace a mano.
- **Un campo mantiene su etiqueta en portugués**: sin `verbose_name` Django arma la etiqueta a partir del nombre, así que un campo renombrado al inglés mostraría "created by" en las pantallas y en la auditoría. Un campo renombrado dice su propia etiqueta (`_("criado por")`); si no, una prueba falla (decisión 170).
- **Las pruebas vigilan las plantillas**: una variable que una plantilla busca y no encuentra hace fallar la ejecución, salvo que esté en `tests/missing_template_variables.txt` (decisión 159). Un renombrado mantiene esa lista igual, con los nombres nuevos.

## Modelos (hecho)

| Antes | Después | Label de la app |
|---|---|---|
| `Agendamento` | `Appointment` | `agenda` |
| `TipoAtendimento` | `AppointmentType` | `agenda` |
| `RegistroAuditoria` | `AuditEntry` | `auditoria` |
| `CodigoRecuperacao` | `RecoveryCode` | `conta` |
| `DuasEtapas` | `TwoFactor` | `conta` |
| `Carteirinha` | `MemberCard` | `convenios` |
| `Convenio` | `HealthPlan` | `convenios` |
| `Clinica` | `Clinic` | `core` |
| `ModuloDaClinica` | `ClinicModule` | `core` |
| `Vinculo` | `Membership` | `core` |
| `Caixa` | `CashRegister` | `financeiro` |
| `Categoria` | `Category` | `financeiro` |
| `CentroCusto` | `CostCenter` | `financeiro` |
| `Comissao` | `Commission` | `financeiro` |
| `Conta` | `FinancialAccount` | `financeiro` |
| `Fechamento` | `BookClosing` | `financeiro` |
| `Fornecedor` | `Supplier` | `financeiro` |
| `GrupoContabil` | `AccountGroup` | `financeiro` |
| `ImportacaoExtrato` | `StatementImport` | `financeiro` |
| `Lancamento` | `Entry` | `financeiro` |
| `MovimentoCaixa` | `CashMovement` | `financeiro` |
| `Pagamento` | `Payment` | `financeiro` |
| `Parcela` | `Installment` | `financeiro` |
| `Planejamento` | `Planning` | `financeiro` |
| `TransacaoBancaria` | `BankTransaction` | `financeiro` |
| `ItemOrcamento` | `EstimateItem` | `orcamentos` |
| `Orcamento` | `Estimate` | `orcamentos` |
| `Procedimento` | `Procedure` | `orcamentos` |
| `Paciente` | `Patient` | `pacientes` |
| `PessoaRelacionada` | `RelatedPerson` | `pacientes` |
| `Folha` | `Payroll` | `pessoal` |
| `Funcionario` | `Employee` | `pessoal` |
| `Salario` | `Salary` | `pessoal` |
| `Profissional` | `Practitioner` | `profissionais` |
| `Adendo` | `Addendum` | `prontuario` |
| `Anexo` | `Attachment` | `prontuario` |
| `Atendimento` | `Visit` | `prontuario` |
| `Atestado` | `Certificate` | `prontuario` |
| `PedidoDeExames` | `ExamRequest` | `prontuario` |
| `Receita` | `Prescription` | `prontuario` |
| `Rechamada` | `Recall` | `rechamadas` |
| `Bairro` | `Neighborhood` | `referencias` |
| `Banco` | `Bank` | `referencias` |
| `Cidade` | `City` | `referencias` |
| `EstadoCivil` | `MaritalStatus` | `referencias` |
| `Logradouro` | `Street` | `referencias` |
| `UF` | `State` | `referencias` |

## Campos, primer lote

Los nombres que se repiten entre los modelos, en cuatro partes. **Hecho:** `clinica`, `criado_em`/`criada_em`, `alterado_em`/`alterada_em` y `criado_por` (decisión 160), `paciente`, `profissional` y `usuario` (decisión 161), `nome`, `ativo`/`ativa`, `codigo`, `descricao`, `observacoes`, `observacao`, `telefone` y `numero` (decisión 163), `tipo`, `valor`, `situacao`, `atendimento` y `lancamento` (decisión 164), `data` y `conta` (decisión 165), los 19 nombres después de `conta` en la tabla (decisión 166; también las variables locales con esos nombres exactos, como `clinica` → `clinic`). Después, los campos propios de cada app y, por último, las funciones y variables.

| Antes | Después |
|---|---|
| `clinica` | `clinic` |
| `paciente` | `patient` |
| `profissional` | `practitioner` |
| `usuario` | `user` |
| `nome` | `name` |
| `criado_em`, `criada_em` | `created_at` |
| `alterado_em`, `alterada_em` | `updated_at` |
| `criado_por` | `created_by` |
| `ativo`, `ativa` | `active` |
| `tipo` | `kind` |
| `valor` | `amount` |
| `codigo` | `code` |
| `data` | `date` |
| `descricao` | `description` |
| `observacoes` | `notes` |
| `observacao` | `note` |
| `telefone` | `phone` |
| `situacao` | `status` |
| `numero` | `number` |
| `atendimento` | `visit` |
| `lancamento` | `entry` |
| `conta` | `account` |
| `arquivo` | `file` |
| `ate` | `until` |
| `bairro` | `neighborhood` |
| `categoria` | `category` |
| `cidade` | `city` |
| `cor` | `color` |
| `cpf_cnpj` | `tax_id` |
| `desconto` | `discount` |
| `inicio`, `fim` | `start`, `end` |
| `funcionario` | `employee` |
| `grupo` | `group` |
| `momento` | `timestamp` |
| `motivo` | `reason` |
| `razao_social` | `legal_name` |
| `registro` | `registration` |
| `tamanho` | `size` |
| `uf` | `state` |
| `validade` | `valid_until` |

## Campos de cada app

Los campos propios de cada app, una app a la vez. **Hecho:** finanzas (decisión 167), pacientes (decisión 168), core e historia clínica (decisión 169), y las otras nueve apps (decisión 171): todo campo de modelo tiene ahora nombre en inglés.

### Finanzas (`financeiro`)

| Antes | Después |
|---|---|
| `saldo_inicial` | `opening_balance` |
| `pai` | `parent` |
| `centro_custo` | `cost_center` |
| `pessoa` | `payer` |
| `fornecedor` | `supplier` |
| `valor_total` | `total_amount` |
| `cancelado`, `cancelada` | `cancelled` |
| `cancelado_em` | `cancelled_at` |
| `cancelado_por` | `cancelled_by` |
| `motivo_cancelamento` | `cancellation_reason` |
| `vencimento` | `due_date` |
| `parcela` | `installment` |
| `juros` | `interest` |
| `forma` | `method` |
| `cartao_bandeira` | `card_brand` |
| `cartao_parcelas` | `card_installments` |
| `cartao_codigo` | `card_transaction_code` |
| `estornado` | `reversed` |
| `estornado_em` | `reversed_at` |
| `estornado_por` | `reversed_by` |
| `motivo_estorno` | `reversal_reason` |
| `comissao` | `commission` |
| `comissao_estorno` | `commission_reversal` |
| `aberto_em` | `opened_at` |
| `aberto_por` | `opened_by` |
| `valor_abertura` | `opening_amount` |
| `fechado_em` | `closed_at` |
| `fechado_por` | `closed_by` |
| `valor_esperado` | `expected_amount` |
| `valor_contado` | `counted_amount` |
| `caixa` | `cash_register` |
| `outra_conta` | `other_account` |
| `percentual` | `percentage` |
| `recebido` | `received_amount` |
| `estornos` | `reversal_deduction` |
| `ano` | `year` |
| `banco` | `bank_code` |
| `conta_no_banco` | `bank_account_number` |
| `saldo` | `balance` |
| `saldo_em` | `balance_date` |
| `novas` | `new_transactions` |
| `repetidas` | `duplicate_transactions` |
| `ignoradas` | `unreadable_transactions` |
| `importacao` | `statement_import` |
| `pagamento` | `payment` |
| `movimento` | `cash_movement` |
| `conciliado_por` | `reconciled_by` |
| `conciliado_em` | `reconciled_at` |

### Pacientes (`pacientes`)

| Antes | Después |
|---|---|
| `inscricao_estadual` | `state_registration` |
| `sexo` | `sex` |
| `data_nascimento` | `birth_date` |
| `estado_civil` | `marital_status` |
| `profissao` | `occupation` |
| `responsavel` | `guardian` |
| `telefone_celular` | `mobile_phone` |
| `telefone_residencial` | `home_phone` |
| `telefone_comercial` | `work_phone` |
| `cep` | `postal_code` |
| `estado_nome` | `state_name` |
| `cidade_nome` | `city_name` |
| `logradouro` | `street` |
| `complemento` | `complement` |
| `arquivado` | `archived` |
| `arquivado_em` | `archived_at` |
| `arquivado_por` | `archived_by` |
| `vinculo` | `relationship` |
| `outro_paciente` | `other_patient` |

`rg` queda: es el nombre del documento brasileño, como `cpf`.

### Core (`core`)

| Antes | Después |
|---|---|
| `idioma` | `language` |
| `ultima_versao_vista` | `last_seen_version` |
| `demonstracao` | `demo` |
| `documento` | `document` |
| `endereco` | `address` |
| `moeda` | `currency` |
| `pais` | `country` |
| `fuso_horario` | `time_zone` |
| `numeracao_dentaria` | `tooth_numbering` |
| `exigir_duas_etapas` | `require_two_factor` |
| `agenda_inicio` | `schedule_start` |
| `agenda_fim` | `schedule_end` |
| `agenda_intervalo` | `schedule_interval` |
| `papel` | `role` |

`area` ya está en inglés.

### Historia clínica (`prontuario`)

| Antes | Después |
|---|---|
| `agendamento` | `appointment` |
| `queixa_principal` | `chief_complaint` |
| `historia` | `present_illness` |
| `antecedentes` | `medical_history` |
| `exame_fisico` | `physical_exam` |
| `conduta` | `plan` |
| `finalizado_em` | `finalized_at` |
| `finalizado_por` | `finalized_by` |
| `texto` | `text` |
| `hora_inicio` | `start_time` |
| `hora_fim` | `end_time` |
| `dias` | `days` |
| `prescricao` | `medications` |
| `exames` | `exams` |
| `indicacao` | `indication` |
| `conteudo` | `content` |

### Personal (`pessoal`)

| Antes | Después |
|---|---|
| `cpf` | `tax_id` |
| `cargo` | `job_title` |
| `admissao` | `hired_on` |
| `desligamento` | `left_on` |
| `desde` | `effective_from` |
| `competencia` | `period` |
| `salario` | `salary` |
| `horas_extras` | `overtime_hours` |
| `valor_hora_extra` | `overtime_rate` |
| `faltas` | `absences` |

### Presupuestos (`orcamentos`)

| Antes | Después |
|---|---|
| `decidido_em` | `decided_at` |
| `decidido_por` | `decided_by` |
| `orcamento` | `estimate` |
| `procedimento` | `procedure` |
| `dentes` | `teeth` |
| `quantidade` | `quantity` |
| `valor_unitario` | `unit_price` |

### Auditoría (`auditoria`)

| Antes | Después |
|---|---|
| `usuario_nome` | `user_name` |
| `acao` | `action` |
| `modelo` | `model_name` |
| `objeto_id` | `object_id` |
| `objeto_descricao` | `object_repr` |
| `alteracoes` | `changes` |

### Cuenta (inicio de sesión en dos pasos) (`conta`)

| Antes | Después |
|---|---|
| `segredo` | `secret` |
| `ativada_em` | `activated_at` |
| `ultimo_passo` | `last_step` |
| `resumo` | `digest` |
| `usado_em` | `used_at` |

### Seguros médicos (`convenios`)

| Antes | Después |
|---|---|
| `convenio` | `health_plan` |
| `plano` | `plan` |
| `beneficiario` | `member_code` |
| `titular` | `holder` |

### Datos de referencia (`referencias`)

| Antes | Después |
|---|---|
| `sigla` | `abbreviation` |
| `regiao` | `region` |
| `nome_curto` | `short_name` |
| `ordem` | `sort_order` |

### Profesionales (`profissionais`)

| Antes | Después |
|---|---|
| `comissao_percentual` | `commission_percentage` |

### Llamadas de control (`rechamadas`)

| Antes | Después |
|---|---|
| `concluida` | `done` |

### Agenda (`agenda`)

| Antes | Después |
|---|---|
| `serie` | `series` |

## Funciones y variables

La última parte del plan (decisión 159): las funciones, métodos, clases, constantes y variables. **Aquí solo cambian nombres de Python**: las cadenas quedan, y con ellas las claves de contexto de las plantillas, los nombres de consulta, las claves de JSON y los valores guardados, con los que el nombre de una variable solo coincide. Los campos declarados de un formulario mantienen su nombre (son los nombres enviados), y los nombres que una URL pasa a la vista y el `parametrize` de una prueba siguen a los parámetros de la función. **Hecho:** las variables comunes a varias apps (decisión 172), la app core (decisión 173), finanzas (decisión 174), agenda (decisión 175), pacientes, historia clínica, presupuestos, personal, llamadas de control, seguros médicos, profesionales y equipo (decisión 176), legado, auditoría, cuenta, ayuda, odontología, monitoreo y datos de referencia (decisión 177), y las releases (decisión 178): los nombres de Python de todas las apps están en inglés.

### Variables comunes

| Antes | Después |
|---|---|
| `resposta` | `response` |
| `dados` | `data` |
| `pagina` | `page` |
| `linha` | `row` |
| `linhas` | `rows` |
| `campo` | `field` |
| `campos` | `fields` |
| `hoje` | `today` |
| `recepcao` | `reception` |
| `lista` | `results` |
| `dia` | `day` |
| `busca` | `search` |
| `chave` | `key` |
| `atual` | `current` |
| `anterior` | `previous` |
| `erro` | `error` |
| `novo` | `new` |
| `outro` | `other` |
| `antes` | `before` |
| `depois` | `after` |
| `contexto` | `context` |
| `rotulo` | `label` |
| `antigo` | `old` |
| `padrao` | `default` |
| `mensagem` | `message` |
| `caminho` | `path` |
| `senha` | `password` |
| `hora` | `hour` |
| `origem` | `source` |
| `agora` | `now` |
| `mes` | `month` |
| `sessao` | `session` |
| `resumo` | `summary` |
| `filtros` | `filters` |
| `primeiro` | `first` |
| `ultimo` | `last` |
| `objeto` | `obj` |
| `tabela` | `table` |
| `tabelas` | `tables` |
| `coluna` | `column` |
| `limite` | `limit` |
| `configuracao` | `config` |
| `opcoes` | `options` |
| `posicao` | `position` |
| `semana` | `week` |
| `aviso` | `warning` |
| `duracao` | `duration` |
| `exemplo` | `example` |
| `de` | `since` |

`itens` queda por ahora: también es el acceso inverso del presupuesto y el formato de las releases.

### Core (`core`): clases

| Antes | Después |
|---|---|
| `VinculoNaClinicaInline` | `ClinicMembershipInline` |
| `VinculoDoUsuarioInline` | `UserMembershipInline` |
| `ClinicaAdmin` | `ClinicAdmin` |
| `UsuarioAdmin` | `ClinicUserAdmin` |
| `VinculoAdmin` | `MembershipAdmin` |
| `Pais` | `Country` |
| `Documento` | `Document` |
| `Documentos` | `Documents` |
| `_Invalido` | `_Invalid` |
| `Guarda` | `Retention` |
| `Legislacao` | `Legislation` |
| `SemClinicaAtual` | `NoCurrentClinic` |
| `ClinicaDiferente` | `WrongClinic` |
| `FiltroClinicaAtual` | `CurrentClinicFilter` |
| `ClinicaManager` | `ClinicManager` |
| `ModeloDaClinica` | `ClinicModel` |
| `CampoDecimal` | `LocalizedDecimalField` |
| `FormularioBootstrap` | `BootstrapForm` |
| `TrocaSenhaForm` | `ChangePasswordForm` |
| `ModulosClinicosForm` | `ClinicModulesForm` |
| `ClinicaForm` | `ClinicForm` |
| `NovaClinicaForm` | `NewClinicForm` |
| `ClinicaAdminForm` | `ClinicAdminForm` |
| `Alerta` | `Alert` |
| `Migracao` | `MigrationEntry` |
| `ClinicaAtualMiddleware` | `CurrentClinicMiddleware` |
| `ProxyReversoMiddleware` | `ReverseProxyMiddleware` |
| `IdiomaDoUsuarioMiddleware` | `UserLanguageMiddleware` |
| `ModuloClinico` | `ModuleCode` |
| `Papel` | `Role` |
| `Modulo` | `Module` |
| `Acao` | `Action` |
| `TrocarSenhaView` | `ChangePasswordView` |

### Core: miembros de los enums

| Antes | Después |
|---|---|
| `RECEPCAO` | `FRONT_DESK` |
| `PROFISSIONAL` | `PRACTITIONER` |
| `FINANCEIRO` | `FINANCE` |
| `ODONTOLOGIA` | `DENTISTRY` |
| `MEDICINA` | `MEDICINE` |
| `AGENDA` | `SCHEDULE` |
| `PRONTUARIO` | `MEDICAL_RECORDS` |
| `ORCAMENTOS` | `ESTIMATES` |
| `RECHAMADAS` | `RECALLS` |
| `ANIVERSARIANTES` | `BIRTHDAYS` |
| `CONVENIOS` | `HEALTH_PLANS` |
| `PESSOAL` | `STAFF` |
| `PACIENTES` | `PATIENTS` |
| `PROFISSIONAIS` | `PRACTITIONERS` |
| `CADASTROS` | `CATALOGS` |
| `USUARIOS` | `USERS` |
| `CLINICA` | `CLINIC` |
| `AUDITORIA` | `AUDIT` |
| `RECEBIMENTOS` | `RECEIVING` |
| `VER` | `VIEW` |
| `CRIAR` | `CREATE` |
| `ALTERAR` | `CHANGE` |
| `EXCLUIR` | `DELETE` |
| `VISUALIZAR` | `VIEWED` |
| `LOGIN_FALHOU` | `LOGIN_FAILED` |

### Core: constantes

| Antes | Después |
|---|---|
| `BACKUP_ATRASADO_APOS` | `BACKUP_LATE_AFTER` |
| `PADRAO` | `DEFAULT` |
| `PAISES` | `COUNTRIES` |
| `ESCOLHAS` | `CHOICES` |
| `ESCOLHAS_FUSO` | `TIME_ZONE_CHOICES` |
| `FUSO_PADRAO` | `DEFAULT_TIME_ZONE` |
| `_DEZ_DIGITOS` | `_TEN_DIGITS` |
| `_TELEFONE` | `_PHONE` |
| `_CEP` | `_POSTAL_CODE` |
| `MOEDAS` | `CURRENCIES` |
| `SIMBOLOS` | `SYMBOLS` |
| `LIMITE` | `LIMIT` |
| `DIAS_ORCAMENTO` | `ESTIMATE_DAYS` |
| `DIAS_A_PAGAR` | `PAYABLE_DAYS` |
| `PAPEIS` | `DOCUMENT_ROLES` |
| `DOCUMENTOS` | `DOCUMENTS` |
| `ESTADO` | `STATE` |
| `PROVINCIA` | `PROVINCE` |
| `LEIS` | `LAWS` |
| `FIXAS` | `FIXED` |
| `ARQUIVO` | `FILE_NAME` |
| `LIMITE_COMENTARIO` | `COMMENT_LIMIT` |
| `APAGA` | `DELETES` |
| `QUEBRA_VOLTA` | `BREAKS_ROLLBACK` |
| `SEM_VOLTA` | `NO_ROLLBACK` |
| `REVISAR` | `REVIEW` |
| `ALTERADA` | `CHANGED` |
| `CLINICAS_ANTIGAS` | `OLD_CLINICS` |
| `USUARIOS_ANTIGOS` | `OLD_USERS` |
| `CLINICAS` | `CLINICS` |
| `ESPECIALIDADES` | `SPECIALTIES` |
| `MODULOS_GERAIS` | `GENERAL_MODULES` |
| `DEPENDENCIAS` | `DEPENDENCIES` |
| `ALFABETICA` | `ALPHABETICAL` |
| `_TODAS` | `_ALL` |
| `_VER` | `_VIEW` |
| `_SEM_EXCLUIR` | `_NO_DELETE` |
| `MATRIZ` | `MATRIX` |
| `SO_LEITURA_NA_DEMONSTRACAO` | `READ_ONLY_IN_DEMO` |
| `MODULO_DA_CLINICA` | `CLINIC_MODULE` |
| `PREFIXO_IPV6` | `IPV6_PREFIX` |
| `INTERVALOS` | `INTERVALS` |
| `RFC_PESSOA` | `RFC_PERSON` |
| `RFC_EMPRESA` | `RFC_COMPANY` |

### Core: funciones y métodos

| Antes | Después |
|---|---|
| `_somente_superusuario` | `_superuser_only` |
| `idiomas` | `languages` |
| `inatividade` | `inactivity` |
| `_cidade` | `_city` |
| `pais_da_clinica` | `clinic_country` |
| `do_codigo` | `by_code` |
| `variante_do_idioma` | `language_variant` |
| `normalizar_telefone_internacional` | `normalize_international_phone` |
| `formatar_telefone` | `format_phone` |
| `_formatar_telefone_latino` | `_format_latin_phone` |
| `link_whatsapp` | `whatsapp_link` |
| `normalizar_cep` | `normalize_postal_code` |
| `formatar_cep` | `format_postal_code` |
| `rotulo_cep` | `postal_code_label` |
| `moeda_da_clinica` | `clinic_currency` |
| `formatar` | `format_amount` |
| `simbolo` | `symbol` |
| `montar` | `build` |
| `_agenda` | `_schedule` |
| `_rechamadas` | `_recalls` |
| `_aniversariantes` | `_birthdays` |
| `_orcamentos` | `_estimates` |
| `_soma_dos_saldos` | `_sum_of_balances` |
| `_recebimentos` | `_receipts` |
| `_financeiro` | `_finance` |
| `_valido` | `_valid` |
| `_opcoes` | `_options` |
| `_sem_milhar` | `_without_thousands` |
| `campo_documento` | `document_field` |
| `documento_por_tipo` | `document_by_kind` |
| `_pais_escolhido` | `_chosen_country` |
| `_ajustar_ao_pais` | `_adjust_to_country` |
| `_escolhidos` | `_chosen` |
| `_agendamento_fora` | `_appointment_outside` |
| `_exigir` | `_require` |
| `_milhares` | `_thousands` |
| `normalizar` | `normalize` |
| `valido` | `is_valid` |
| `escrever` | `write` |
| `do_papel` | `for_role` |
| `_escrever_cpf` | `_write_cpf` |
| `_escrever_cnpj` | `_write_cnpj` |
| `_escrever_cedula_uy` | `_write_cedula_uy` |
| `_escrever_bn` | `_write_bn` |
| `_escrever_medicare` | `_write_medicare` |
| `do_pais` | `for_country` |
| `papeis` | `roles` |
| `identificar` | `identify` |
| `sigla` | `abbreviation` |
| `invalido` | `invalid` |
| `limpar` | `clean_value` |
| `_clinica_atual` | `_current_clinic` |
| `_isolamento_desligado` | `_isolation_off` |
| `clinica_atual` | `current_clinic` |
| `isolamento_ativo` | `isolation_active` |
| `usar_clinica` | `use_clinic` |
| `sem_isolamento` | `without_isolation` |
| `todos` | `all_objects` |
| `_conferir_clinica` | `_check_clinic` |
| `prazo_de_guarda` | `retention_period` |
| `_fixa` | `_is_fixed` |
| `campos_de_data` | `date_fields` |
| `_conta` | `_account` |
| `_rotulos` | `_labels` |
| `migracoes_do_diff` | `migrations_from_diff` |
| `_campo` | `_field` |
| `_tabelas` | `_tables` |
| `_so_o_nome` | `_name_only` |
| `_depois` | `_after` |
| `_so_aumenta` | `_only_grows` |
| `_coluna_obrigatoria_sem_default` | `_required_column_without_default` |
| `alertas_da_operacao` | `operation_alerts` |
| `analisar` | `analyze` |
| `banco_descartavel` | `disposable_database` |
| `_migrar` | `_migrate` |
| `_erro` | `_error` |
| `ida_e_volta` | `round_trip` |
| `_linhas_da_migracao` | `_migration_lines` |
| `_alteradas` | `_changed` |
| `alertas` | `alerts` |
| `_usuario` | `_user` |
| `_pacientes` | `_patients` |
| `_carteirinhas` | `_member_cards` |
| `_funcionarios` | `_employees` |
| `_relacionados` | `_related_people` |
| `_agendamentos` | `_appointments` |
| `resolver_clinica` | `resolve_clinic` |
| `_usar_pais_da_clinica` | `_use_clinic_country` |
| `sigla_documento` | `document_abbreviation` |
| `documento_escrito` | `written_document` |
| `odontologia` | `dentistry` |
| `medicina` | `medicine` |
| `modulo_habilitado` | `module_enabled` |
| `unica` | `single` |
| `iniciais` | `initial` |
| `faltando` | `missing` |
| `habilitados` | `enabled` |
| `visiveis` | `visible` |
| `desligados_visiveis` | `visible_disabled` |
| `marcar_se_desligado` | `mark_if_disabled` |
| `configurar` | `configure` |
| `chave_alfabetica` | `alphabetical_key` |
| `pode` | `can` |
| `so_a_propria_agenda` | `own_schedule_only` |
| `tabela_permissoes` | `permissions_table` |
| `exige_permissao` | `requires_permission` |
| `ip_para_bloqueio` | `ip_for_lockout` |
| `modulos_para_clinica_nova` | `modules_for_new_clinic` |
| `rotulo_documento` | `document_label` |
| `simbolo_moeda` | `currency_symbol` |
| `validar_cor` | `validate_color` |
| `somente_digitos` | `digits_only` |
| `normalizar_cnpj` | `normalize_cnpj` |
| `cpf_valido` | `valid_cpf` |
| `cnpj_valido` | `valid_cnpj` |
| `validar_cpf` | `validate_cpf` |
| `validar_cnpj` | `validate_cnpj` |
| `nono_digito` | `ninth_digit` |
| `normalizar_telefone` | `normalize_phone` |
| `_saudacao` | `_greeting` |
| `_destino_seguro` | `_safe_destination` |
| `cadastrar_clinica` | `register_clinic` |
| `configuracoes` | `clinic_settings` |
| `trocar_idioma` | `change_language` |

`Usuario` (el modelo de usuario) mantiene su nombre por ahora (ver abajo).

### Agenda (`agenda`)

| Antes | Después |
|---|---|
| `TipoAtendimentoAdmin` | `AppointmentTypeAdmin` |
| `AgendamentoAdmin` | `AppointmentAdmin` |
| `AgendaConfig` | `ScheduleConfig` |
| `TipoAtendimentoForm` | `AppointmentTypeForm` |
| `AgendamentoForm` | `AppointmentForm` |
| `_alinhado` | `_aligned` |
| `TIPOS_PADRAO` | `DEFAULT_TYPES` |
| `_NOMES_PADRAO_PARA_TRADUCAO` | `_DEFAULT_NAMES_FOR_TRANSLATION` |
| `nome_exibido` | `display_name` |
| `desmarcado` | `is_cancelled` |
| `presenca_marcavel` | `attendance_markable` |
| `AGENDADO` | `BOOKED` |
| `COMPARECEU` | `ATTENDED` |
| `FALTOU` | `MISSED` |
| `DESMARCOU` | `CANCELLED` |
| `criar_tipos_padrao` | `create_default_types` |
| `profissionais_visiveis` | `visible_practitioners` |
| `agendamentos_visiveis` | `visible_appointments` |
| `ocorrencias` | `occurrences` |
| `conflitos` | `conflicts` |
| `tipos_padrao_para_clinica_nova` | `default_types_for_new_clinic` |
| `MOTIVOS_RECHAMADA` | `RECALL_REASONS` |
| `simular_agendamentos` | `simulate_appointments` |
| `_situacao` | `_status` |
| `simular_rechamadas` | `simulate_recalls` |
| `DESCRICOES_FINANCEIRAS` | `FINANCE_DESCRIPTIONS` |
| `simular_financeiro` | `simulate_finance` |
| `DESPESAS_SIMULADAS` | `SIMULATED_EXPENSES` |
| `DESPESAS_DO_ATENDIMENTO` | `VISIT_EXPENSES` |
| `_simular_despesas` | `_simulate_expenses` |
| `PROCEDIMENTOS_EXEMPLO` | `SAMPLE_PROCEDURES` |
| `simular_orcamentos` | `simulate_estimates` |
| `simular_comissoes` | `simulate_commissions` |
| `tipo_novo` | `new_appointment_type` |
| `tipo_editar` | `edit_appointment_type` |
| `tipo_excluir` | `delete_appointment_type` |
| `SESSAO_PROFISSIONAL` | `SESSION_PRACTITIONER` |
| `SESSAO_DATA` | `SESSION_DATE` |
| `_data_lembrada` | `_remembered_date` |
| `_resposta_sucesso` | `_success_response` |
| `_relogio` | `_clock` |
| `MENSAGENS_SITUACAO` | `STATUS_MESSAGES` |
| `_aniversariantes_em` | `_birthdays_on` |
| `aniversariantes_dia` | `birthdays_on_day` |
| `titulo` | `title` |
| `criar` | `create` |
| `marcar` | `mark` |
| `_formulario` | `_type_form` |
| `_periodo` | `_range` |
| `editar` | `edit_appointment` |
| `excluir` | `delete_appointment` |
| `new` | `new_appointment` |
| `tipos` | `appointment_types` |
| `eventos` | `events` |
| `calendario` | `calendar_view` |
| `aniversariantes` | `birthdays` |

### Pacientes, historia clínica, presupuestos, personal, llamadas de control, seguros médicos, profesionales, equipo

| Antes | Después |
|---|---|
| `PacienteAdmin` | `PatientAdmin` |
| `PacientesConfig` | `PatientsConfig` |
| `UFField` | `StateField` |
| `CidadeField` | `CityField` |
| `_campo_texto` | `_text_field` |
| `PacienteForm` | `PatientForm` |
| `SO_NO_BRASIL` | `BRAZIL_ONLY` |
| `FORA_DO_BRASIL` | `OUTSIDE_BRAZIL` |
| `_limpar_telefone` | `_clean_phone` |
| `PessoaRelacionadaForm` | `RelatedPersonForm` |
| `idade` | `age` |
| `cidade_estado` | `city_state` |
| `telefone_principal` | `main_phone` |
| `Sexo` | `Sex` |
| `FEMININO` | `FEMALE` |
| `MASCULINO` | `MALE` |
| `OUTRO` | `OTHER` |
| `telefone_exibido` | `display_phone` |
| `MAE` | `MOTHER` |
| `PAI` | `FATHER` |
| `RESPONSAVEL` | `GUARDIAN` |
| `CONJUGE` | `SPOUSE` |
| `FILHO` | `CHILD` |
| `IRMAO` | `SIBLING` |
| `AVO` | `GRANDPARENT` |
| `NETO` | `GRANDCHILD` |
| `PARENTE` | `RELATIVE` |
| `EMERGENCIA` | `EMERGENCY` |
| `CONTATO` | `CONTACT` |
| `_ve_arquivados` | `_sees_archived` |
| `_visiveis` | `_visible_patients` |
| `ficha` | `patient_record` |
| `HISTORICO` | `HISTORY` |
| `_historico` | `_history` |
| `arquivar` | `archive` |
| `restaurar` | `restore` |
| `sugestoes` | `suggestions` |
| `MESES` | `MONTH_NAMES` |
| `relacionados_de` | `related_of` |
| `relacionado_novo` | `new_related_person` |
| `relacionado_editar` | `edit_related_person` |
| `_relacionado` | `_related_person_form` |
| `relacionado_remover` | `remove_related_person` |
| `ProntuarioConfig` | `MedicalRecordsConfig` |
| `AtendimentoForm` | `VisitForm` |
| `AdendoForm` | `AddendumForm` |
| `AtestadoForm` | `CertificateForm` |
| `ReceitaForm` | `PrescriptionForm` |
| `PedidoDeExamesForm` | `ExamRequestForm` |
| `TAMANHO_MAXIMO_DO_ANEXO` | `MAX_ATTACHMENT_SIZE` |
| `ASSINATURAS` | `SIGNATURES` |
| `AnexoForm` | `AttachmentForm` |
| `CAMPOS_DA_ANAMNESE` | `ANAMNESIS_FIELDS` |
| `finalizado` | `is_finalized` |
| `COMPARECIMENTO` | `ATTENDANCE` |
| `AFASTAMENTO` | `SICK_LEAVE` |
| `prontuario_habilitado` | `medical_records_enabled` |
| `administra_prontuario` | `manages_medical_records` |
| `acessa_prontuario` | `accesses_medical_records` |
| `profissional_do_usuario` | `user_practitioner` |
| `_profissional` | `_practitioner` |
| `SIGILO` | `CONFIDENTIAL` |
| `exige_profissional` | `requires_practitioner` |
| `_auditar` | `_audit` |
| `_finalizar` | `_finalize` |
| `_do_autor` | `_by_author` |
| `atestado_novo` | `new_certificate` |
| `receita_nova` | `new_prescription` |
| `pedido_de_exames_novo` | `new_exam_request` |
| `anexo_enviar` | `upload_attachment` |
| `anexo_remover` | `remove_attachment` |
| `OrcamentosConfig` | `EstimatesConfig` |
| `ProcedimentoForm` | `ProcedureForm` |
| `OrcamentoForm` | `EstimateForm` |
| `ItemForm` | `EstimateItemForm` |
| `DescontoForm` | `DiscountForm` |
| `AprovarForm` | `ApproveEstimateForm` |
| `VALIDADE_PADRAO` | `DEFAULT_VALIDITY` |
| `validade_padrao` | `default_valid_until` |
| `ABERTO` | `OPEN` |
| `APROVADO` | `APPROVED` |
| `RECUSADO` | `REFUSED` |
| `_conferir_modulo` | `_check_module` |
| `dentes_exibicao` | `teeth_display` |
| `lista_dentes` | `teeth_list` |
| `_liberar_se_desligado` | `_allow_if_disabled` |
| `item_adicionar` | `add_item` |
| `item_remover` | `remove_item` |
| `procedimentos` | `procedures` |
| `procedimento_form` | `procedure_form` |
| `FuncionarioAdmin` | `EmployeeAdmin` |
| `FolhaAdmin` | `PayrollAdmin` |
| `PessoalConfig` | `StaffConfig` |
| `_dinheiro` | `_money` |
| `FuncionarioForm` | `EmployeeForm` |
| `FolhaForm` | `PayrollForm` |
| `LancarForm` | `PostPayrollForm` |
| `HORAS_POR_MES` | `HOURS_PER_MONTH` |
| `ADICIONAL_HORA_EXTRA` | `OVERTIME_PREMIUM` |
| `DIAS_POR_MES` | `DAYS_PER_MONTH` |
| `salario_em` | `salary_on` |
| `valor_horas_extras` | `overtime_amount` |
| `desconto_faltas` | `absence_deduction` |
| `lancada` | `is_posted` |
| `hora_extra_sugerida` | `suggested_overtime_rate` |
| `competencia_de` | `period_of` |
| `fim_do_mes` | `end_of_month` |
| `preparar` | `prepare` |
| `mes_da_url` | `month_from_url` |
| `RechamadaAdmin` | `RecallAdmin` |
| `RechamadasConfig` | `RecallsConfig` |
| `RechamadaForm` | `RecallForm` |
| `ConvenioAdmin` | `HealthPlanAdmin` |
| `CarteirinhaAdmin` | `MemberCardAdmin` |
| `ConveniosConfig` | `HealthPlansConfig` |
| `ConvenioForm` | `HealthPlanForm` |
| `CarteirinhaForm` | `MemberCardForm` |
| `Codigo` | `CodeFormat` |
| `Seguros` | `Insurers` |
| `SEGUROS` | `INSURERS` |
| `com_nome_local` | `with_local_name` |
| `rotulo_do_registro` | `registration_label` |
| `rotulo_do_codigo` | `code_label` |
| `vencida` | `is_expired` |
| `carteirinha_nova` | `new_member_card` |
| `carteirinha_editar` | `edit_member_card` |
| `_carteirinha` | `_member_card_form` |
| `ProfissionalAdmin` | `PractitionerAdmin` |
| `ProfissionaisConfig` | `PractitionersConfig` |
| `ProfissionalForm` | `PractitionerForm` |
| `EquipeConfig` | `TeamConfig` |
| `conta_exclusiva` | `exclusive_account` |
| `NovoMembroForm` | `NewMemberForm` |
| `VinculoForm` | `MembershipForm` |
| `SenhaForm` | `PasswordForm` |
| `_vinculo` | `_membership` |
| `duas_etapas` | `two_factor` |

Las vistas de cada app (renombradas solo dentro de la app, pues el mismo nombre antiguo era una vista distinta en cada una):

`patients`:

| Antes | Después |
|---|---|
| `results` | `patient_list` |
| `new` | `new_patient` |
| `editar` | `edit_patient` |
| `excluir` | `delete_patient` |
| `imprimir` | `print_patient` |
| `_formulario` | `_patient_form` |
| `filtrar` | `filter_patients` |
| `aniversariantes` | `birthdays` |

`medical_records`:

| Antes | Después |
|---|---|
| `prontuario` | `medical_records` |
| `new` | `new_visit` |
| `imprimir` | `print_visit` |
| `_campos` | `_fields` |
| `atestado` | `certificate` |
| `receita` | `prescription` |
| `adendo` | `addendum` |
| `pedido_de_exames` | `exam_request` |
| `anexo` | `attachment` |

`estimates`:

| Antes | Después |
|---|---|
| `vencido` | `is_expired` |
| `_aberto` | `_open_estimate` |
| `_odontologia` | `_dentistry` |
| `results` | `estimate_list` |
| `new` | `new_estimate` |
| `editar` | `edit_estimate` |
| `detalhe` | `estimate_detail` |
| `_dentes` | `_teeth` |
| `aprovar` | `approve` |
| `recusar` | `refuse` |
| `imprimir` | `print_estimate` |

`staff`:

| Antes | Después |
|---|---|
| `lancar` | `post_payroll` |
| `results` | `employee_list` |
| `new` | `new_employee` |
| `editar` | `edit_employee` |
| `_formulario` | `_employee_form` |
| `folha` | `payroll` |

`recalls`:

| Antes | Después |
|---|---|
| `_data` | `_date` |
| `_voltar` | `_back` |
| `results` | `recall_list` |
| `new` | `new_recall` |
| `editar` | `edit_recall` |
| `_formulario` | `_recall_form` |
| `concluir` | `complete` |
| `excluir` | `delete_recall` |
| `do_dia` | `of_day` |

`health_plans`:

| Antes | Después |
|---|---|
| `results` | `health_plan_list` |
| `new` | `new_health_plan` |
| `editar` | `edit_health_plan` |
| `_convenio` | `_health_plan_form` |

`practitioners`:

| Antes | Después |
|---|---|
| `results` | `practitioner_list` |
| `new` | `new_practitioner` |
| `editar` | `edit_practitioner` |
| `_formulario` | `_practitioner_form` |
| `excluir` | `delete_practitioner` |

`team`:

| Antes | Después |
|---|---|
| `results` | `member_list` |
| `new` | `new_member` |
| `editar` | `edit_member` |

### Legado, auditoría, cuenta, ayuda, odontología, monitoreo, datos de referencia

| Antes | Después |
|---|---|
| `OBSERVACOES` | `NOTES` |
| `DESLOCAMENTO_NASCIMENTO` | `BIRTH_DATE_SHIFT` |
| `ClinicaNaoEncontrada` | `ClinicNotFound` |
| `Resultado` | `Result` |
| `_mesmo_tamanho` | `_same_length` |
| `_Anonimizador` | `_Anonymizer` |
| `LegadoConfig` | `LegacyConfig` |
| `DumpInvalido` | `InvalidDump` |
| `ler_tabelas` | `read_tables` |
| `TABELAS` | `TABLES` |
| `DURACAO_MINIMA` | `MIN_DURATION` |
| `ImportacaoRecusada` | `ImportRefused` |
| `Relatorio` | `Report` |
| `_cabe` | `_fits` |
| `_Importador` | `_Importer` |
| `_estados_civis` | `_marital_statuses` |
| `_logradouros` | `_streets` |
| `_ampliar_horario` | `_widen_hours` |
| `_nascimento` | `_birth_date` |
| `RegistroAuditoriaAdmin` | `AuditEntryAdmin` |
| `AuditoriaConfig` | `AuditConfig` |
| `RETENCAO_LOGIN_FALHOU` | `FAILED_LOGIN_RETENTION` |
| `AuditoriaMiddleware` | `AuditMiddleware` |
| `ip_da_requisicao` | `request_ip` |
| `registrar` | `log_event` |
| `nome_do_modelo` | `model_label` |
| `REMOVIDO` | `REMOVED` |
| `anonimizar` | `anonymize` |
| `_clinica_de` | `_clinic_of` |
| `AUDITADOS` | `AUDITED` |
| `IGNORADOS` | `IGNORED` |
| `antes_de_salvar` | `before_save` |
| `depois_de_salvar` | `after_save` |
| `depois_de_excluir` | `after_delete` |
| `_entrou` | `_logged_in` |
| `_saiu` | `_logged_out` |
| `_falhou` | `_login_failed` |
| `tipos_de_registro` | `record_types` |
| `campos_alterados` | `changed_fields` |
| `DuasEtapasAdmin` | `TwoFactorAdmin` |
| `ContaConfig` | `AccountConfig` |
| `EntrarForm` | `LoginForm` |
| `_campo_codigo` | `_code_field` |
| `CodigoForm` | `CodeForm` |
| `DesativarForm` | `DisableTwoFactorForm` |
| `RecuperarSenhaForm` | `RecoverPasswordForm` |
| `NovaSenhaForm` | `NewPasswordForm` |
| `LIVRES` | `EXEMPT_PATHS` |
| `ExigirDuasEtapasMiddleware` | `RequireTwoFactorMiddleware` |
| `LIMITE_POR_ENDERECO` | `LIMIT_PER_ADDRESS` |
| `QUANTOS_CODIGOS` | `CODE_COUNT` |
| `ALFABETO` | `ALPHABET` |
| `tentativas_do_endereco` | `address_attempts` |
| `endereco_bloqueado` | `address_blocked` |
| `ativa_para` | `active_for` |
| `obrigatoria` | `is_required` |
| `endereco_do_app` | `app_uri` |
| `segredo_em_grupos` | `secret_in_groups` |
| `verificar_app` | `verify_app` |
| `_resumo` | `_digest` |
| `novos_codigos` | `new_codes` |
| `verificar_recuperacao` | `verify_recovery` |
| `VALIDADE_PENDENTE` | `PENDING_VALIDITY` |
| `TENTATIVAS_CODIGO` | `CODE_ATTEMPTS` |
| `EntrarView` | `ClinicLoginView` |
| `_com_email` | `_with_email` |
| `recuperar_enviado` | `password_recover_sent` |
| `nova_senha` | `new_password` |
| `senha_redefinida` | `password_reset_done` |
| `AjudaConfig` | `HelpConfig` |
| `documentacao` | `documentation` |
| `PASTAS` | `FOLDERS` |
| `PREFIXOS` | `PREFIXES` |
| `IDIOMA_PADRAO` | `DEFAULT_LANGUAGE` |
| `_ITEM_DE_LISTA` | `_LIST_ITEM` |
| `_idioma` | `_language` |
| `url_do_site` | `site_url` |
| `_separar_listas` | `_split_lists` |
| `PAGINAS` | `PAGES` |
| `para_o_site` | `to_site` |
| `OdontologiaConfig` | `DentistryConfig` |
| `DENTES_PERMANENTES` | `PERMANENT_TEETH` |
| `DENTES_DECIDUOS` | `PRIMARY_TEETH` |
| `DENTES_VALIDOS` | `VALID_TEETH` |
| `NUMERACOES` | `NUMBERINGS` |
| `LEGENDAS` | `LEGENDS` |
| `LETRAS_UNIVERSAIS` | `UNIVERSAL_LETTERS` |
| `_QUADRANTES_PALMER` | `_PALMER_QUADRANTS` |
| `numeracao_da_clinica` | `clinic_numbering` |
| `ordenar` | `sort_teeth` |
| `TIPOS_DE_ATENDIMENTO` | `APPOINTMENT_TYPES` |
| `odontograma` | `odontogram` |
| `nome_dente` | `tooth_name` |
| `legenda_numeracao` | `numbering_legend` |
| `MonitoramentoConfig` | `MonitoringConfig` |
| `alerta` | `health_alert` |
| `CAMPOS` | `FIELDS` |
| `CAMPOS_CONTAINER` | `CONTAINER_FIELDS` |
| `COLETA_PARADA_APOS` | `COLLECTION_STOPPED_AFTER` |
| `LACUNA` | `GAP` |
| `LIMITES` | `THRESHOLDS` |
| `com_rede` | `with_network` |
| `topo_da_escala` | `scale_top` |
| `PERIODOS` | `PERIODS` |
| `GRAFICOS` | `CHARTS` |
| `_banco` | `_database` |
| `UFAdmin` | `StateAdmin` |
| `CidadeAdmin` | `CityAdmin` |
| `BancoAdmin` | `BankAdmin` |
| `EstadoCivilAdmin` | `MaritalStatusAdmin` |
| `ReferenciasConfig` | `ReferenceDataConfig` |
| `opcoes_cidades` | `city_options` |
| `sugestoes_endereco` | `address_suggestions` |

Renombrados solo dentro de su propia app (palabras comunes):

`legacy`:

| Antes | Después |
|---|---|
| `pacientes` | `patients` |
| `agendamentos` | `appointments` |
| `carteirinhas` | `member_cards` |
| `rechamadas` | `recalls` |
| `profissionais` | `practitioners` |
| `funcionarios` | `employees` |
| `fornecedores` | `suppliers` |
| `financeiro` | `finance` |
| `auditoria` | `audit` |
| `executar` | `run` |
| `_nome` | `_name` |
| `_texto` | `_text` |
| `_chave` | `_key` |
| `_data` | `_date` |
| `_hora` | `_time` |
| `_documento` | `_document` |
| `importar` | `import_dump` |
| `_clinica` | `_clinic` |
| `_tipos` | `_types` |
| `_paciente` | `_patient` |
| `_cidades` | `_cities` |
| `_profissionais` | `_practitioners` |
| `_valores` | `_values` |

`audit`:

| Antes | Después |
|---|---|
| `results` | `audit_list` |
| `_data` | `_date` |
| `_valor` | `_value` |
| `_valores` | `_values` |

`monitoring`:

| Antes | Después |
|---|---|
| `ultima` | `latest` |
| `nivel` | `level` |
| `niveis` | `levels` |
| `parada` | `stopped` |
| `amostras` | `samples` |
| `grafico` | `chart` |
| `painel` | `health_dashboard` |
| `_arquivo` | `_file` |
| `_ler` | `_read` |

`account`:

| Antes | Después |
|---|---|
| `verificar` | `verify` |
| `ativar` | `activate` |
| `desativar` | `deactivate` |
| `recuperar` | `password_recover` |

`help`:

| Antes | Después |
|---|---|
| `privacidade` | `privacy` |

`reference_data`:

| Antes | Después |
|---|---|
| `cidades` | `cities` |
| `bancos` | `banks` |

### Releases (`novidades`)

| Antes | Después |
|---|---|
| `TIPOS` | `KINDS` |
| `MODULOS` | `MODULES` |
| `IDIOMA_ORIGEM` | `SOURCE_LANGUAGE` |
| `PUBLICOS` | `AUDIENCES` |
| `ORIGENS` | `SOURCES` |
| `REPOSITORIO` | `REPOSITORY` |
| `ReleasesInvalidas` | `InvalidReleases` |
| `_no_idioma` | `_in_language` |
| `url_pr` | `pr_url` |
| `itens_para` | `items_for` |
| `versao_para_tupla` | `version_tuple` |
| `_textos` | `_texts` |
| `_validar_item` | `_validate_item` |
| `_validar_release` | `_validate_release` |
| `ler_releases` | `read_releases` |
| `versao_atual` | `current_version` |
| `tem_novidade_para` | `has_news_for` |
| `para_publico` | `for_audience` |
| `listar_releases` | `list_releases` |
| `novidades_router` | `whats_new_router` |
| `todas` | `all_releases` |
| `NovidadesConfig` | `WhatsNewConfig` |
| `versao` (context processor) | `version_context` |
| `chave` | `key` |
| `lista` (view) | `whats_new_list` |

La interfaz pública mantiene sus nombres: los campos de la API (`versao`, `data`, `titulo`, `itens`, `tipo`, `tipo_nome`, `modulo`, `texto`, `origem`, `pr`) y los nombres de consulta (`publico`, `desde`), y las claves de `releases.yaml`, que reflejan los atributos de la release y la página.

### Finanzas (`financeiro`): clases

| Antes | Después |
|---|---|
| `FinanceiroConfig` | `FinanceConfig` |
| `LancamentoReceberForm` | `ReceivableEntryForm` |
| `LancamentoPagarForm` | `PayableEntryForm` |
| `FornecedorForm` | `SupplierForm` |
| `PlanejamentoForm` | `PlanningForm` |
| `FecharForm` | `CloseBooksForm` |
| `ReabrirForm` | `ReopenBooksForm` |
| `ReceberForm` | `ReceivePaymentForm` |
| `MotivoForm` | `ReasonForm` |
| `GrupoContabilForm` | `AccountGroupForm` |
| `CategoriaForm` | `CategoryForm` |
| `CentroCustoForm` | `CostCenterForm` |
| `ContaForm` | `FinancialAccountForm` |
| `AbrirCaixaForm` | `OpenCashRegisterForm` |
| `MovimentoCaixaForm` | `CashMovementForm` |
| `FecharCaixaForm` | `CloseCashRegisterForm` |
| `PercentualComissaoForm` | `CommissionPercentageForm` |
| `PagarComissaoForm` | `PayCommissionForm` |
| `ImportarExtratoForm` | `ImportStatementForm` |
| `LancamentoDaTransacaoForm` | `TransactionEntryForm` |
| `TipoFinanceiro` | `FinancialKind` |
| `ParcelaQuerySet` | `InstallmentQuerySet` |
| `ArquivoInvalido` | `InvalidFile` |
| `Transacao` | `Transaction` |
| `Extrato` | `Statement` |
| `Formas` | `Methods` |
| `Candidato` | `Candidate` |

### Finanzas: clases y miembros de los enums

| Antes | Después |
|---|---|
| `Tipo` | `Kind` |
| `Situacao` | `Status` |
| `Forma` | `Method` |
| `BANCO` | `BANK` |
| `CARTAO` | `CARD` |
| `RECEITA` | `INCOME` |
| `DESPESA` | `EXPENSE` |
| `FISICA` | `INDIVIDUAL` |
| `JURIDICA` | `COMPANY` |
| `RECEBER` | `RECEIVABLE` |
| `PAGAR` | `PAYABLE` |
| `DINHEIRO` | `CASH` |
| `DEBITO` | `DEBIT` |
| `CREDITO` | `CREDIT` |
| `TRANSFERENCIA` | `TRANSFER` |
| `CARTEIRA` | `WALLET` |
| `DEBITO_AUTOMATICO` | `DIRECT_DEBIT` |
| `FINANCIAMENTO` | `FINANCING` |
| `RETIRADA` | `WITHDRAWAL` |
| `REFORCO` | `TOP_UP` |
| `PENDENTE` | `PENDING` |
| `CONCILIADA` | `RECONCILED` |
| `IGNORADA` | `IGNORED` |

### Finanzas: constantes

| Antes | Después |
|---|---|
| `CENTAVO` | `CENT` |
| `DATA` | `DATE_INPUT` |
| `DIVIDIR` | `SPLIT` |
| `REPETIR` | `REPEAT` |
| `TAMANHO_MAXIMO_OFX` | `MAX_OFX_SIZE` |
| `CONTAS_PADRAO` | `DEFAULT_ACCOUNTS` |
| `CATEGORIAS_PADRAO` | `DEFAULT_CATEGORIES` |
| `PLANO_PADRAO` | `DEFAULT_CHART` |
| `CARTOES` | `CARDS` |
| `_LATINA` | `_LATIN` |
| `FORMAS` | `METHODS` |
| `_INGLES_COM_CHEQUE` | `_ENGLISH_WITH_CHEQUE` |
| `JANELA` | `WINDOW` |
| `FAIXAS_DE_ATRASO` | `OVERDUE_BRACKETS` |
| `POR_PAGINA` | `PER_PAGE` |
| `SITUACOES` | `STATUSES` |
| `MOVIMENTOS_NA_URL` | `URL_MOVEMENTS` |

### Finanzas: funciones, métodos y vistas

| Antes | Después |
|---|---|
| `percentual_de` | `percentage_for` |
| `_creditos` | `_credits` |
| `_debitos` | `_debits` |
| `pendente` | `pending` |
| `pagar` | `pay` |
| `liberar` | `release` |
| `_formas_com_vazio` | `_methods_with_blank` |
| `_campo_dinheiro` | `_money_field` |
| `_centros_de_custo` | `_cost_centers` |
| `_grupos` | `_groups` |
| `_descendentes` | `_descendants` |
| `ancestrais` | `ancestors` |
| `criar_padroes` | `create_defaults` |
| `papel_documento` | `document_role` |
| `nome_pessoa` | `payer_name` |
| `com_saldo` | `with_balance` |
| `abertas` | `unpaid` |
| `valores` | `paid_and_balance` |
| `aberto` | `is_open` |
| `diferenca` | `difference` |
| `bruta` | `gross` |
| `entrada` | `is_incoming` |
| `_texto` | `_text` |
| `_data` | `_date` |
| `_valor` | `_amount` |
| `ler` | `read` |
| `em_uso` | `in_use` |
| `rotulos` | `labels` |
| `importar` | `import_statement` |
| `outra_conta_no_banco` | `other_bank_account` |
| `candidatos` | `candidates` |
| `_vincular` | `_link` |
| `_pendente` | `_pending` |
| `conciliar` | `reconcile` |
| `conciliar_unicos` | `reconcile_unique` |
| `criar_lancamento` | `create_entry` |
| `ignorar` | `ignore` |
| `desfazer` | `undo` |
| `saldo_no_sistema` | `system_balance` |
| `dividir` | `split` |
| `somar_meses` | `add_months` |
| `receber` | `receive` |
| `estornar` | `reverse_payment` |
| `cancelar` | `cancel` |
| `fechado_ate` | `closed_until` |
| `conferir_periodo` | `check_period` |
| `fechar` | `close_books` |
| `reabrir` | `reopen_books` |
| `devedores` | `debtors` |
| `resumo_do_paciente` | `patient_summary` |
| `_sinal` | `_sign` |
| `pagamentos_validos` | `valid_payments` |
| `saldos_das_contas` | `account_balances` |
| `fluxo_de_caixa` | `cash_flow` |
| `recebido_e_pago` | `received_and_paid` |
| `relatorio` | `report` |
| `ligar_grupos` | `link_groups` |
| `em_ordem_de_arvore` | `in_tree_order` |
| `totais_por_grupo` | `totals_by_group` |
| `arvore_por_grupo` | `tree_by_group` |
| `fracao_do_ano` | `year_fraction` |
| `planejamento` | `planning` |
| `salvar_metas` | `save_targets` |
| `copiar_metas` | `copy_targets` |
| `caixa_aberto` | `open_cash_register` |
| `abrir_caixa` | `open_register` |
| `resumo_do_caixa` | `register_summary` |
| `movimentar_caixa` | `move_cash` |
| `fechar_caixa` | `close_register` |
| `padroes_para_clinica_nova` | `defaults_for_new_clinic` |
| `_modulo` | `_module` |
| `receber_lista` | `receivables` |
| `pagar_lista` | `payables` |
| `_lista` | `_entry_list` |
| `lancamento_novo` | `new_entry` |
| `despesa_nova` | `new_expense` |
| `lancamento_cancelar` | `cancel_entry` |
| `recibo` | `receipt` |
| `caixa_detalhe` | `cash_register_detail` |
| `caixa_movimento` | `cash_movement_view` |
| `caixa_fechar` | `close_cash_register` |
| `_periodo` | `_period` |
| `relatorios` | `reports` |
| `fechamento` | `book_closing` |
| `cadastro_lista` | `catalog_list` |
| `cadastro_form` | `catalog_form` |
| `plano_contas` | `chart_of_accounts` |
| `grupo_novo` | `new_group` |
| `grupo_editar` | `edit_group` |
| `_grupo_form` | `_group_form` |
| `fornecedores` | `suppliers` |
| `fornecedor_novo` | `new_supplier` |
| `fornecedor_editar` | `edit_supplier` |
| `_fornecedor_form` | `_supplier_form` |
| `_ate` | `_until` |
| `comissoes_lista` | `commission_list` |
| `comissao_pagar` | `pay_commission` |
| `extratos` | `statements` |
| `extrato` | `statement` |
| `_voltar_ao_extrato` | `_back_to_statement` |
| `extrato_conciliar_unicos` | `statement_reconcile_unique` |
| `transacao_acao` | `transaction_action` |
| `transacao_lancamento` | `transaction_entry` |

Las clases de enum `Tipo`, `Situacao` y `Forma` de todas las apps pasaron a `Kind`, `Status` y `Method`, como sus campos `kind`, `status`, `method`; los miembros de las demás apps siguen con su app.

## Configuración, clases CSS y ganchos del HTML (hecho)

La configuración de `config/settings.py` y los nombres que comparten las plantillas, la hoja de estilos y los scripts (decisión 182). Una clase armada a partir de un valor guardado mantiene el valor: `status-compareceu`, `kind-novo`. Los ids de campos de filtro con el nombre de su query (`de`, `agrupar`) siguieron a la query en la decisión 184 (`since`, `group`).

### Configuración

| Antes | Después |
|---|---|
| `NOME_SISTEMA` | `SYSTEM_NAME` |
| `RELEASES_ARQUIVO` | `RELEASES_FILE` |
| `INATIVIDADE_MINUTOS` | `IDLE_MINUTES` |
| `RECUPERAR_SENHA_POR_EMAIL` | `PASSWORD_RECOVERY_BY_EMAIL` |
| `env_renomeada` | `env_renamed` |
| `env_lista` | `env_list` |

### Clases CSS

| Antes | Después |
|---|---|
| `amostra-cor` | `color-swatch` |
| `amostra-cor-pequena` | `color-swatch-small` |
| `bandeira` | `flag` |
| `busca-paciente` | `patient-search` |
| `busca-paciente-sugestoes` | `patient-search-suggestions` |
| `busca-paciente-texto` | `patient-search-text` |
| `deciduos` | `primary-teeth` |
| `dente` | `tooth` |
| `documento` | `document` |
| `grade` | `grid-line` |
| `grafico` | `chart` |
| `indicador` | `indicator` |
| `indicador-rotulo` | `indicator-label` |
| `indicador-valor` | `indicator-value` |
| `legenda` | `legend` |
| `legenda-tipo` | `type-legend` |
| `linha-1` | `line-1` |
| `linha-2` | `line-2` |
| `logo-barra` | `logo-bar` |
| `logo-entrada` | `logo-login` |
| `meio` | `middle` |
| `nome-clinica` | `clinic-name` |
| `odontograma` | `odontogram` |
| `odontograma-interativo` | `odontogram-interactive` |
| `odontograma-linha` | `odontogram-row` |
| `odontograma-rolagem` | `odontogram-scroll` |
| `qr-codigo` | `qr-code` |
| `recibo` | `receipt` |
| `recibo-estornado` | `receipt-reversed` |
| `rodape` | `site-footer` |
| `selecionado` | `selected` |
| `seletor-idioma` | `language-selector` |
| `so-pf` | `pf-only` |
| `so-pj` | `pj-only` |
| `texto-clinico` | `clinical-text` |
| `situacao-<valor>` | `status-<valor>` |
| `tipo-<valor>` | `kind-<valor>` |
| `saude-<nivel>` | `health-<nivel>` |

### Ids del HTML

| Antes | Después |
|---|---|
| `aviso-agenda` | `schedule-notice` |
| `bairros-sugeridos` | `suggested-neighborhoods` |
| `busca-inicio` | `home-search` |
| `configuracao-agenda` | `schedule-settings` |
| `escopo-este` | `scope-this` |
| `escopo-serie` | `scope-series` |
| `form-paciente` | `patient-form` |
| `form-sair` | `logout-form` |
| `ir-para-data` | `go-to-date` |
| `logradouros-sugeridos` | `suggested-streets` |
| `modal-agenda` | `schedule-modal` |
| `modal-conteudo` | `schedule-modal-content` |
| `sugestoes-endereco` | `address-suggestions` |
| `calendario` | `calendar` |
| `ate` | `until` |
| `profissional` | `practitioner` |

### Atributos data-

| Antes | Después |
|---|---|
| `data-aviso-inatividade` | `data-idle-warning` |
| `data-com-olho` | `data-password-toggle` |
| `data-dente` | `data-tooth` |
| `data-enviar-ao-mudar` | `data-submit-on-change` |
| `data-exemplo-pf` | `data-example-pf` |
| `data-exemplo-pj` | `data-example-pj` |
| `data-imprimir` | `data-print` |
| `data-inatividade` | `data-idle-minutes` |
| `data-mostrar-senha` | `data-show-password` |
| `data-ocultar-senha` | `data-hide-password` |
| `data-paciente-id` | `data-patient-id` |
| `data-paciente-nome` | `data-patient-name` |
| `data-rotulo-pf` | `data-label-pf` |
| `data-rotulo-pj` | `data-label-pj` |
| `data-url-ativo` | `data-url-active` |
| `data-url-saiu` | `data-url-logged-out` |

## Nombres de los scripts (hecho)

Las variables locales y funciones de los scripts de `static/js` (`evento` → `event`, `campo` → `field`, `abrirModal` → `openModal`) y los nombres que el script de la agenda comparte con el servidor (decisión 183). Los valores guardados que los scripts comparan quedan como están (`"desmarcou"`, `"agendado"`).

### Configuración de la agenda (`schedule-settings`)

| Antes | Después |
|---|---|
| `intervalo` | `interval` |
| `agora` | `now` |
| `textos` | `texts` |
| `textos.aniversariantes` | `texts.birthdays` |
| `textos.rechamadas` | `texts.recalls` |
| `pode.criar` | `can.create` |
| `pode.alterar` | `can.change` |
| `urls.eventos` | `urls.events` |
| `urls.novo` | `urls.new` |
| `urls.aniversariantes` | `urls.birthdays` |
| `urls.aniversariantes_dia` | `urls.birthdays_today` |
| `urls.rechamadas` | `urls.recalls` |
| `urls.rechamadas_dia` | `urls.recalls_today` |

### Evento, almacenamiento y marcadores

| Antes | Después | Dónde |
|---|---|---|
| `agendaAtualizada` | `scheduleUpdated` | evento HTMX que el servidor envía después de guardar (`HX-Trigger`) |
| `mensagem` | `message` | su texto |
| `kaladrius-atividade` | `kaladrius-activity` | clave del `localStorage` de la última actividad |
| `aniversariantes` | `birthday-badge` | clase del marcador de cumpleaños |
| `rechamadas` | `recall-badge` | clase del marcador de rellamadas |

## Campos de formulario y nombres de consulta (hecho)

Los campos de formulario que no son campo de modelo, los nombres que las pantallas envían en la dirección o en un formulario (`?de=` → `?since=`, `name="acao"` → `name="action"`) y los prefijos de los formularios de la verificación en dos pasos (decisión 184). Los valores quedan: `?group=mes`, `action=finalizar`, `scope=serie`, como los valores guardados. Una dirección de antes de la decisión 155 se redirige con los nombres antiguos de consulta traducidos (`/financeiro/fluxo-de-caixa/?de=…&agrupar=mes` → `/finance/cash-flow/?since=…&group=mes`).

### Campos de formulario

| Antes | Después |
|---|---|
| `senha` | `password` |
| `salario_desde` | `salary_since` |
| `parcelas` | `installments` |
| `primeiro_vencimento` | `first_due_date` |
| `recebido_agora` | `received_now` |
| `pago_agora` | `paid_now` |
| `modo` | `mode` |
| `modulos` | `modules` |
| `modulos_gerais` | `general_modules` |
| `repeticoes` | `repetitions` |

### Nombres de consulta y de formulario

| Antes | Después |
|---|---|
| `pagina` | `page` |
| `de` | `since` |
| `mes` | `month` |
| `periodo` | `period` |
| `agrupar` | `group` |
| `modulo` | `module` |
| `novo` | `new` |
| `inatividade` | `idle` |
| `acao` | `action` |
| `escopo` | `scope` |
| `chave` | `key` |

### Prefijos de formulario

| Antes | Después |
|---|---|
| `desativar` | `disable` |
| `codigos` | `codes` |

## Nombres del contexto de las plantillas (hecho)

Los nombres que las vistas y los procesadores de contexto pasan a las plantillas, y las variables de las propias plantillas (`{% for %}`, `{% with %}`, `as`), en todas las plantillas (decisión 185): `{{ nome_sistema }}` → `{{ system_name }}`, `pode.agenda.ver` → `can.agenda.ver`, `pagina` → `page`. Quedan: las claves dentro de un valor (`dashboard.rechamadas`, y los códigos de módulo y acción en `can.agenda.ver`), los marcadores dentro de `{% blocktranslate %}`, que forman parte del texto traducido; cuando uno venía de un nombre renombrado, la etiqueta lo liga al nuevo (`{% blocktranslate with versao_sistema=system_version %}`). El bloque `titulo` pasó a ser `title` en la decisión 187.

| Antes | Después |
|---|---|
| `abertas` | `open_items` |
| `aberto` | `is_open` |
| `acoes` | `actions` |
| `adendo` | `addendum` |
| `adendo_form` | `addendum_form` |
| `adendos` | `addenda` |
| `administra` | `is_admin` |
| `agenda` | `schedule` |
| `agendamentos` | `appointments` |
| `ajuda` | `help_text` |
| `ajuda_paciente` | `patient_help` |
| `anexo` | `attachment` |
| `anexo_form` | `attachment_form` |
| `anexos` | `attachments` |
| `aniversariantes` | `birthdays` |
| `ano_anterior` | `previous_year` |
| `anterior` | `previous` |
| `antes` | `before` |
| `arvore` | `tree` |
| `arvores` | `trees` |
| `atendimentos` | `visits` |
| `atestado` | `certificate` |
| `atestados` | `certificates` |
| `ativada` | `enabled` |
| `backup_atrasado` | `backup_late` |
| `backup_nenhum` | `backup_missing` |
| `bairros` | `neighborhoods` |
| `banco` | `database` |
| `bruta` | `gross` |
| `busca` | `search` |
| `cadastro` | `catalog` |
| `calculo` | `calculation` |
| `campo` | `field` |
| `campos` | `fields` |
| `carteirinha` | `plan_card` |
| `carteirinhas` | `plan_cards` |
| `cidades` | `cities` |
| `classe` | `css_class` |
| `clinica_atual` | `current_clinic` |
| `codigos` | `codes` |
| `configuracao` | `schedule_settings` |
| `contas` | `accounts` |
| `convenios` | `health_plans` |
| `data_documento` | `document_date` |
| `data_longa` | `long_date` |
| `decidua` | `primary_row` |
| `deciduos` | `primary_rows` |
| `dente` | `tooth` |
| `depois` | `after` |
| `desativar` | `disable_form` |
| `desconto_form` | `discount_form` |
| `detalhe` | `detail` |
| `dia` | `day` |
| `dica_busca` | `search_hint` |
| `diferenca` | `difference` |
| `documento_fiscal` | `tax_document` |
| `documentos` | `documents` |
| `documentos_do_pais` | `country_documents` |
| `duas_etapas` | `two_factor` |
| `editavel` | `editable` |
| `em_aberto` | `outstanding` |
| `emite_documentos` | `issues_documents` |
| `endereco_bloqueado` | `address_locked` |
| `erro` | `error` |
| `erro_situacao` | `status_error` |
| `esperado` | `expected` |
| `exclusiva` | `exclusive` |
| `fechado_ate` | `closed_until` |
| `fechar_form` | `close_form` |
| `filtros` | `filters` |
| `fin` | `finances` |
| `financeiro` | `finance` |
| `fluxo` | `flow` |
| `folha` | `payslip` |
| `folhas` | `payslips` |
| `funcionarios` | `employees` |
| `grafico` | `chart` |
| `graficos` | `charts` |
| `historico` | `history` |
| `hoje` | `today` |
| `idade` | `age` |
| `idioma_atual` | `current_language` |
| `idioma_base` | `base_language` |
| `idioma_nome` | `language_name` |
| `idiomas` | `languages` |
| `inatividade_minutos` | `idle_minutes` |
| `instancia` | `instance` |
| `interativo` | `interactive` |
| `inverso` | `inverse` |
| `itens` | `items` |
| `lancar_form` | `post_form` |
| `legenda` | `legend` |
| `lei` | `law` |
| `ligado_desde` | `up_since` |
| `linha` | `row` |
| `linhas` | `rows` |
| `logradouros` | `streets` |
| `mensagem` | `message` |
| `meses` | `months` |
| `modelo` | `model` |
| `modelos` | `model_names` |
| `modulo_desligado` | `disabled_module` |
| `modulos` | `modules` |
| `modulos_desligados` | `disabled_modules` |
| `mostrar_dentes` | `show_teeth` |
| `niveis` | `levels` |
| `nivel` | `level` |
| `no_brasil` | `in_brazil` |
| `nome_sistema` | `system_name` |
| `novos` | `codes_form` |
| `objeto` | `subject` |
| `obrigatoria` | `required` |
| `odontologia_habilitada` | `dentistry_enabled` |
| `opcao` | `option` |
| `orcamentos` | `estimates` |
| `outro` | `other` |
| `pacientes` | `patients` |
| `pagamentos` | `payments` |
| `pagar` | `payable` |
| `pagina` | `page` |
| `painel` | `dashboard` |
| `parada` | `stopped` |
| `parametros` | `query` |
| `parcelas` | `installments` |
| `pedido` | `exam_request` |
| `pedidos` | `exam_requests` |
| `pendentes` | `pending` |
| `permanentes` | `permanent_rows` |
| `pode` | `can` |
| `pode_alterar` | `can_change` |
| `pode_aprovar` | `can_approve` |
| `pode_desconto` | `can_discount` |
| `pode_excluir` | `can_delete` |
| `pode_prontuario` | `can_open_record` |
| `prazo_de_guarda` | `retention_period` |
| `procedimentos` | `procedures` |
| `profissionais` | `practitioners` |
| `prontuario` | `medical_record` |
| `proximo` | `following` |
| `proximo_ano` | `next_year` |
| `proximos` | `following_count` |
| `reabrir_form` | `reopen_form` |
| `receb` | `receipts` |
| `receita` | `prescription` |
| `receitas` | `prescriptions` |
| `rechamada` | `recall` |
| `rechamadas` | `recalls` |
| `recuperar_por_email` | `recovery_by_email` |
| `relacionada` | `related` |
| `relacionados` | `related_people` |
| `relatorio` | `report` |
| `remove_anexos` | `can_remove_attachments` |
| `restantes` | `remaining` |
| `resumo` | `summary` |
| `rotulo` | `label` |
| `rotulo_do_registro` | `registration_label` |
| `salario_atual` | `current_salary` |
| `salarios` | `salaries` |
| `saldo_sistema` | `system_balance` |
| `saudacao` | `greeting` |
| `saude_alerta` | `health_alert` |
| `secao` | `section` |
| `secoes` | `sections` |
| `selecionados` | `selected` |
| `sem_percentual` | `without_percentage` |
| `sigla` | `abbreviation` |
| `situacoes` | `statuses` |
| `so_a_propria` | `own_only` |
| `tabela` | `table` |
| `tem_metas_anteriores` | `has_previous_targets` |
| `tipos` | `types` |
| `titulo` | `title` |
| `titulo1` | `title1` |
| `titulo2` | `title2` |
| `titulo3` | `title3` |
| `titulo4` | `title4` |
| `titulo5` | `title5` |
| `titulo6` | `title6` |
| `titulo_documento` | `document_title` |
| `titulo_g1` | `title_g1` |
| `titulo_g2` | `title_g2` |
| `total_a_vencer` | `total_upcoming` |
| `total_pago` | `total_paid` |
| `total_parcelas` | `total_installments` |
| `total_saldo` | `total_balance` |
| `total_vencido` | `total_overdue` |
| `transacao` | `transaction` |
| `transacoes` | `transactions` |
| `ufs` | `states` |
| `ultima` | `latest` |
| `unicos` | `unique` |
| `url_documentacao` | `docs_url` |
| `url_manual` | `manual_url` |
| `url_situacao` | `status_url` |
| `usado` | `used` |
| `valor` | `value` |
| `versao_nova` | `new_version` |
| `versao_sistema` | `system_version` |
| `versoes` | `versions` |
| `vinculo` | `membership` |
| `vinculo_atual` | `current_membership` |
| `vinculos` | `memberships` |
| `voltar` | `back_entry` |

## Claves dentro de los valores (hecho)

Las claves de los diccionarios que los servicios y las vistas arman para las pantallas (el resumen del inicio, el flujo de caja, los informes, la planificación, las comisiones, la caja, los deudores, la salud del servidor), los atributos que las vistas agregan a los objetos y los campos de la tabla de legislación (decisión 186): `dashboard.rechamadas` → `dashboard.recalls`, `row.vencido` → `row.overdue`, `law.curta` → `law.short_name`. La salud del servidor usa los nombres que graba `health.sh` (`time`, `memory_total`…); las líneas del formato antiguo, con nombres en portugués, se siguen leyendo. Quedan: los códigos de módulo y de acción (`can.agenda.ver`), los papeles de los documentos (`country_documents.paciente`), y los marcadores de los textos traducidos (`%(anos)s`).

### Claves de diccionario

| Antes | Después |
|---|---|
| `a_pagar` | `payable` |
| `a_receber` | `receivable` |
| `a_seguir` | `upcoming` |
| `a_vencer` | `not_yet_due` |
| `abertas` | `unpaid` |
| `agenda` | `schedule` |
| `agora` | `now` |
| `amostras` | `samples` |
| `aniversariantes` | `birthdays` |
| `anteriores` | `past` |
| `ate_anterior` | `previous_until` |
| `atrasadas` | `late` |
| `atrasado` | `late` |
| `bruta` | `gross` |
| `caixas` | `cash_registers` |
| `campo` | `field` |
| `carga` | `load` |
| `centros` | `centers` |
| `compareceram` | `attended` |
| `contas_a_pagar` | `payable_count` |
| `cpu_maxima` | `cpu_max` |
| `cpu_media` | `cpu_avg` |
| `cpu_roubada` | `cpu_steal` |
| `creditos` | `credits` |
| `criticos` | `critical` |
| `debitos` | `debits` |
| `descontos` | `discounts` |
| `desmarcaram` | `cancelled` |
| `despesas_por_categoria` | `expenses_by_category` |
| `despesas_por_centro` | `expenses_by_center` |
| `despesas_por_grupo` | `expenses_by_group` |
| `disco` | `disk` |
| `disco_pct` | `disk_pct` |
| `disco_total` | `disk_total` |
| `disco_usado` | `disk_used` |
| `em_dia` | `on_track` |
| `entradas` | `incoming` |
| `entradas_previstas` | `expected_incoming` |
| `enviado` | `sent` |
| `esperado` | `expected` |
| `faixas` | `brackets` |
| `faltaram` | `missed` |
| `faltas_mes` | `missed_pct_month` |
| `financeiro` | `finance` |
| `fracao` | `fraction` |
| `grupos` | `groups` |
| `hoje` | `today` |
| `inicio_anterior` | `previous_start` |
| `legendas` | `legends` |
| `ligado_ha` | `uptime` |
| `linhas` | `rows` |
| `lista` | `items` |
| `mais_antigo` | `oldest` |
| `marcados_mes` | `booked_month` |
| `memoria` | `memory` |
| `memoria_disponivel` | `memory_available` |
| `memoria_maxima` | `memory_max` |
| `memoria_pct` | `memory_pct` |
| `memoria_total` | `memory_total` |
| `memoria_usada` | `memory_used` |
| `meta` | `target` |
| `momento` | `time` |
| `mostrar_profissional` | `show_practitioner` |
| `movimentos` | `movements` |
| `nivel` | `level` |
| `nome` | `name` |
| `orcamentos` | `estimates` |
| `pacientes` | `patients` |
| `pagamentos` | `payments` |
| `pago_hoje` | `paid_today` |
| `pago_mes` | `paid_month` |
| `parada` | `stopped` |
| `parcelas_a_receber` | `receivable_count` |
| `parcelas_vencidas` | `overdue_count` |
| `por_categoria` | `by_category` |
| `por_centro` | `by_center` |
| `por_forma` | `by_method` |
| `por_grupo` | `by_group` |
| `por_profissional` | `by_practitioner` |
| `proximo` | `next` |
| `proximos` | `upcoming` |
| `realizado` | `actual` |
| `recebido` | `received` |
| `recebido_mes` | `received_month` |
| `recebimentos` | `receipts` |
| `rechamadas` | `recalls` |
| `rede_entrada` | `network_in` |
| `rede_enviado` | `network_sent` |
| `rede_maxima` | `network_max` |
| `rede_recebido` | `network_received` |
| `rede_saida` | `network_out` |
| `reforcos` | `top_ups` |
| `registros` | `row_count` |
| `resultado` | `result` |
| `resultado_anterior` | `previous_result` |
| `resultado_hoje` | `result_today` |
| `resultado_mes` | `result_month` |
| `retiradas` | `withdrawals` |
| `rotulo` | `label` |
| `saidas` | `outgoing` |
| `saidas_previstas` | `expected_outgoing` |
| `saldo_contas` | `account_balances` |
| `saldo_final` | `closing_balance` |
| `sem_coleta` | `no_samples` |
| `sem_grupo` | `ungrouped` |
| `sem_marcacao` | `unmarked` |
| `swap_livre` | `swap_free` |
| `swap_maximo` | `swap_max` |
| `swap_usado` | `swap_used` |
| `tabelas` | `tables` |
| `titulo` | `title` |
| `topo` | `top` |
| `totais` | `totals` |
| `total_pago` | `total_paid` |
| `total_recebido` | `total_received` |
| `unidade` | `unit` |
| `vencido` | `overdue` |

### Atributos que agregan las vistas

| Antes | Después |
|---|---|
| `comissao_devolvida` | `commission_returned` |
| `lista_pagamentos` | `payment_list` |
| `pacientes` (`health_plan`)` | `patient_count` |
| `pago` | `paid` |
| `pendentes` | `pending` |
| `salario_atual` | `current_salary` |

### Legislación

| Antes | Después |
|---|---|
| `anos` | `years` |
| `ate_idade` | `until_age` |
| `autoridade` | `authority` |
| `curta` | `short_name` |
| `fiscal` | `tax_document` |
| `fonte` | `source` |
| `guarda` | `retention` |
| `lei` | `name` |
| `varia` | `varies` |

## Fixtures y variables de las pruebas (hecho)

Los nombres de Python que definen las pruebas (decisión 188): las fixtures, las funciones auxiliares, sus parámetros, las variables locales, las constantes y las claves de los diccionarios `scenario`, unos 450 nombres en 62 archivos. Los datos ficticios quedan en portugués, como las pantallas (`"Maria Paciente"`, `"Clínica fictícia"`, los usuarios `recepcao` y `admin`), igual que los nombres que una prueba lee de los objetos del propio sistema (`release.versao`, `entry.parcelas`). Los compartidos:

| Antes | Después |
|---|---|
| `HOJE` | `TODAY` |
| `ONTEM` | `YESTERDAY` |
| `agendar` | `book` |
| `amostra` | `sample` |
| `carteirinha` | `plan_card` |
| `cenario` | `scenario` |
| `cliente` | `user_client` |
| `cliente_de` | `client_for` |
| `clinica_a` | `clinic_a` |
| `clinica_b` | `clinic_b` |
| `criar_orcamento` | `create_estimate` |
| `criar_profissional` | `create_practitioner` |
| `criar_usuario` | `create_user` |
| `dados_clinica` | `clinic_data` |
| `entrar` | `log_in` |
| `incluir` | `add_item` |
| `lancamento_com` | `entry_with` |
| `no_pais` | `in_country` |
| `parcelas_de` | `installments_of` |

### Claves de `scenario`

| Antes | Después |
|---|---|
| `agenda` | `schedule` |
| `canal` | `channel` |
| `cliente` | `client` |
| `despesa` | `expense` |
| `receita` | `income` |
| `recepcao` | `reception` |
| `tratamento` | `treatment` |

## Campos de las novedades (hecho)

Los campos de `releases.yaml`, del código que lo lee y de la API `/api/v1/releases` (decisión 189). Los valores quedan en portugués, como los guardados: los tipos (`novo`, `melhoria`, `correcao`, `seguranca`), los públicos (`equipe`, `paciente`), los módulos (`Agenda`) y `source: dependabot`. La API todavía acepta `publico` y `desde`; una entrada escrita con los campos antiguos se rechaza, con el nombre del campo a renombrar. El antiguo `/api/v1/versao` queda como estaba (decisión 155).

### `releases.yaml`

| Antes | Después |
|---|---|
| `versao` | `version` |
| `data` | `date` |
| `titulo` | `title` |
| `itens` | `items` |
| `itens[].tipo` | `items[].kind` |
| `itens[].modulo` | `items[].module` |
| `itens[].publico` | `items[].audience` |
| `itens[].texto` | `items[].text` |
| `itens[].origem` | `items[].source` |

### `/api/v1/releases`

| Antes | Después |
|---|---|
| `versao` | `version` |
| `data` | `date` |
| `titulo` | `title` |
| `itens` | `items` |
| `tipo` | `kind` |
| `tipo_nome` | `kind_name` |
| `modulo` | `module` |
| `texto` | `text` |
| `origem` | `source` |
| `?publico=` | `?audience=` |
| `?desde=` | `?since=` |

## Nombres de las relaciones inversas (hecho)

Los nombres de las relaciones inversas, `related_name` (decisión 190): `estimate.itens` → `estimate.items`, `entry.parcelas` → `entry.installments`, `user.vinculos` → `user.memberships`, y lo mismo en las consultas (`vinculos__clinic` → `memberships__clinic`). Solo cambia el estado de Django: las 12 migraciones `*_english_related_names` no generan SQL. Los nombres parecidos que no son relaciones inversas quedan: los códigos de módulo (`can.orcamentos.ver`), las etiquetas de las apps, los nombres en plural de los modelos que se muestran en pantalla.

| Antes | Después |
|---|---|
| `adendos` | `addenda` |
| `agendamentos` | `appointments` |
| `anexos` | `attachments` |
| `atendimentos` | `visits` |
| `atestados` | `certificates` |
| `bairros` | `neighborhoods` |
| `caixas` | `cash_registers` |
| `carteirinhas` | `member_cards` |
| `categorias` | `categories` |
| `cidades` | `cities` |
| `codigos_recuperacao` | `recovery_codes` |
| `comissoes` | `commissions` |
| `duas_etapas` | `two_factor` |
| `filhos` | `children` |
| `folha` | `payroll` |
| `folhas` | `payrolls` |
| `importacoes` | `statement_imports` |
| `itens` | `items` |
| `lancamentos` | `entries` |
| `logradouros` | `streets` |
| `movimentos` | `movements` |
| `orcamentos` | `estimates` |
| `pagamentos` | `payments` |
| `pagamentos_estornados` | `reversed_payments` |
| `parcelas` | `installments` |
| `pedidos_de_exames` | `exam_requests` |
| `profissionais` | `practitioners` |
| `receitas` | `prescriptions` |
| `rechamadas` | `recalls` |
| `relacionado_a` | `related_to` |
| `relacionados` | `related_people` |
| `salarios` | `salaries` |
| `transacao` | `transaction` |
| `transacoes` | `transactions` |
| `vinculos` | `memberships` |

## Nombres que se habían quedado atrás (hecho)

Las variables locales, los parámetros, los atributos de dataclasses, los alias de módulos y los destinos de las opciones de los comandos que las rondas anteriores dejaron pasar (decisión 191), encontrados con un diccionario de portugués y uno de inglés: 429 nombres, como `parcelas` → `installments`, `transacao` → `bank_transaction` y `desde` → `since`. Los argumentos de URL `acao` y `cadastro` pasaron a `action` y `catalog`. Las opciones de línea de comandos siguen iguales: solo cambiaron los nombres que Django pasa a los comandos. Quedan: los roles de los documentos (`paciente`, `empresa`, `pessoa`, `funcionario`, que también son códigos), las funciones de migraciones antiguas que las pruebas llaman, los nombres propios (`BOLETO`, `CEDULA_UY`, ciudades), los valores guardados y los marcadores de los textos traducidos.

| Antes | Después |
|---|---|
| `a_pagar` | `payable` |
| `a_receber` | `receivable` |
| `abertas` | `unpaid` |
| `aberto` | `is_open` |
| `acao` | `action` |
| `aceitos` | `accepted` |
| `achado` | `found_match` |
| `ACOES` | `ACTIONS` |
| `administra` | `manages` |
| `agendamentos` | `appointments` |
| `agrupar` | `group_by` |
| `ajuda_views` | `help_views` |
| `alertas_op` | `op_alerts` |
| `alteradas` | `changed` |
| `alterados` | `changed_ones` |
| `altura` | `height` |
| `alvo` | `target` |
| `alvo_conta` | `target_account` |
| `amostra` | `sample` |
| `analisadas` | `analyzed` |
| `ano` | `year` |
| `apagadas` | `deleted` |
| `apagados` | `deleted_ones` |
| `arvores` | `trees` |
| `assinatura` | `signature` |
| `atencao` | `warning` |
| `atendimentos` | `visits` |
| `atraso` | `delay` |
| `atribuicoes` | `assignments` |
| `_auditoria_senha` | `_password_audit` |
| `avisos` | `warnings` |
| `bairros` | `neighborhoods` |
| `_banco_responde` | `_database_answers` |
| `bloco` | `block` |
| `bruto` | `raw` |
| `cabecalho` | `header` |
| `cadastro` | `record` |
| `CADASTRO` | `CATALOG_PATTERN` |
| `cadeia` | `chain` |
| `CAIXA` | `CASH_KINDS` |
| `calculo` | `calculation` |
| `candidato` | `candidate` |
| `caractere` | `character` |
| `carteirinha` | `member_card` |
| `carteirinhas` | `member_cards` |
| `casas` | `places` |
| `_casas` | `_places` |
| `categorias` | `categories` |
| `celular` | `mobile` |
| `centro` | `cost_center` |
| `centros` | `cost_centers` |
| `_chave` | `_key` |
| `chaves` | `keys` |
| `cidades` | `cities` |
| `classe` | `css_class` / `form_class` |
| `clinicas` | `clinics` |
| `cobertos` | `covered` |
| `codificacao` | `encoding` |
| `codigo_do_cartao` | `card_code` |
| `codigos` | `codes` |
| `colunas` | `columns` |
| `com_paciente` | `with_patient` |
| `comeca` | `starts` |
| `comentario` | `comment` |
| `comissoes` | `commissions` |
| `compacto` | `compact` |
| `condicao` | `condition` |
| `conexao` | `db_connection` |
| `confirmar` | `confirm` |
| `consulta` | `query` |
| `conta_padrao` | `default_account` |
| `conta_servicos` | `account_services` |
| `conta_views` | `account_views` |
| `contagem` | `counts` |
| `contas` | `accounts` |
| `contas_a_pagar` | `payable_count` / `bill_methods` |
| `convenios` | `health_plans` |
| `copia` | `duplicate` |
| `copiadas` | `copied` |
| `corte` | `cut_note` |
| `creditos` | `credit_rows` |
| `criadas` | `created_recalls` |
| `criado` | `created` |
| `_criado` | `_created` |
| `criados` | `created_count` |
| `criar_profissional` | `create_practitioner` |
| `critico` | `critical` |
| `criticos` | `critical` |
| `da_clinica` | `of_clinic` |
| `debito` | `debit` |
| `debitos` | `debits` |
| `decorador` | `decorator` |
| `dente` | `tooth` |
| `desalinhado` | `misaligned` |
| `descer` | `walk_down` |
| `desconhecidos` | `unknown` |
| `descontou` | `deducted` |
| `_descricao` | `_description` |
| `desde` | `since` |
| `despesas` | `expenses` |
| `deste` | `of_patient` |
| `destino` | `destination` |
| `dias_antes` | `days_before` |
| `dias_depois` | `days_after` |
| `digitos` | `digits` |
| `dispositivo` | `device` |
| `do_autor` | `by_author` |
| `do_dia` | `of_the_day` |
| `do_tipo` | `of_kind` |
| `documentos` | `documents` |
| `documentos_da_clinica` | `clinic_documents` |
| `em_aberto` | `outstanding` |
| `em_codigo` | `as_code` |
| `email_invalido` | `invalid_email` |
| `empresa` (in `document_by_kind`) | `company` |
| `encaminhado` | `forwarded` |
| `encontrado` | `found_one` |
| `encontrados` | `found` |
| `entradas` | `inflows` |
| `enviado` | `sent` |
| `era_admin_ativo` | `was_active_admin` |
| `erro_de_novo` | `error_again` |
| `erros` | `errors` |
| `escolhida` | `chosen` |
| `escolhido` | `chosen_one` |
| `escolhidos` | `chosen_ones` |
| `espanhol` | `spanish` |
| `esperado` | `expected` |
| `estado` | `state` |
| `estados_civis` | `marital_statuses` |
| `estorno` | `reversal` |
| `excluido` | `deleted_one` |
| `excluidos` | `excluded` |
| `excluir` | `exclude` |
| `exclusiva` | `exclusive` |
| `exclusoes` | `exclusions` |
| `exemplos` | `examples` |
| `existente` | `existing_one` |
| `existentes` | `existing` |
| `expressoes` | `expressions` |
| `faixa` | `band` |
| `falhar_se_existir` | `fail_if_exists` |
| `falhas` | `failures` |
| `faltaram` | `missed` |
| `feitas` | `done` |
| `feito` | `finished` |
| `fila` | `queue` |
| `filhos` | `children` |
| `filtro` | `query_filter` |
| `fim_anterior` | `previous_end` |
| `fim_do_dia` | `end_of_day` |
| `fim_do_mes_passado` | `end_of_last_month` |
| `financeiro` | `finance_services` |
| `folha` | `payroll` |
| `_folha` | `_payroll` |
| `folhas` | `payrolls` |
| `forcar` | `force` |
| `_forma` | `_method` |
| `formas` | `methods` |
| `formularios` | `form_list` |
| `fracao` | `fraction` |
| `funcionarios` | `employees` |
| `fuso` | `time_zone` |
| `fusos` | `time_zones` |
| `futuros` | `future` |
| `gerar` | `generate` |
| `graficos` | `charts` |
| `grupo_da_categoria` | `category_group` |
| `grupo_de` | `group_of` |
| `grupos` | `groups` |
| `historico` | `history` |
| `horas` | `hours` |
| `ids_agendamentos` | `appointment_ids` |
| `ids_carteirinhas` | `member_card_ids` |
| `ids_clinicas` | `clinic_ids` |
| `ids_itens` | `item_ids` |
| `ids_lancamentos` | `entry_ids` |
| `ids_orcamentos` | `estimate_ids` |
| `ids_pagamentos` | `payment_ids` |
| `ids_parcelas` | `installment_ids` |
| `ids_rechamadas` | `recall_ids` |
| `ids_relacionadas` | `related_person_ids` |
| `ids_usuarios` | `user_ids` |
| `ignorar` | `ignore` |
| `importacoes` | `imports` |
| `individuo` | `individual` |
| `ingles` | `english` |
| `inicial` | `initial` |
| `inicio_anterior` | `previous_start` |
| `inicio_do_mes` | `month_start` |
| `inicio_mes` | `month_start` |
| `inicios` | `starts_list` |
| `instancia` | `instance` |
| `intervalo` | `interval` |
| `intervalos` | `intervals` |
| `inversos` | `inverse` |
| `juridica` | `is_company` |
| `lado` | `side` |
| `lancadas` | `posted` |
| `lancamentos` | `entries` |
| `lancar_form` | `post_form` |
| `largura` | `width` |
| `legado` | `legacy` |
| `legenda` | `legend` |
| `_legenda` | `_legend` |
| `lembrada` | `remembered` |
| `letras` | `letters` |
| `liberado` | `allowed` |
| `lidas` | `parsed` |
| `ligados` | `enabled` |
| `limpo` | `clean` |
| `livre` | `free` |
| `logradouros` | `streets` |
| `mapa` | `mapping` |
| `marcado` | `marked` |
| `marcados` | `booked` |
| `margem` | `margin` |
| `maximo` | `maximum` |
| `meio` | `middle` |
| `meses` | `months` |
| `mesmo_numero` | `same_number` |
| `metas` | `goals` |
| `metodos` | `payment_methods` |
| `migracao` | `migration` |
| `migracoes` | `migrations` |
| `milhar` | `thousands` |
| `minimo` | `minimum` |
| `minutos` | `minutes` |
| `modelo` | `model` |
| `modelos` | `model_list` |
| `modulo_desligado` | `module_off` |
| `_modulos_habilitados` | `_enabled_modules` |
| `movimentos` | `movements` |
| `nascimento` | `birth_date` |
| `nivel` | `level` |
| `nome_arquivo` | `file_name` |
| `nome_cidade` | `city_name` |
| `nome_clinica` | `clinic_name` |
| `nomes` | `names` |
| `nomes_usuarios` | `deleted_usernames` |
| `novos` | `new_ones` |
| `numeracao` | `numbering` |
| `obrigatorio` | `required` |
| `ocupacao` | `occupancy` |
| `ocupado` | `busy` |
| `ocupados` | `busy_slots` |
| `odontologia_desligada_liberada` | `dentistry_off_allowed` |
| `onde` | `where` |
| `operacao` | `operation` |
| `operacoes` | `operations` |
| `orcamentos` | `estimates` |
| `outra` | `other` |
| `OUTRA` | `OTHER` |
| `outra_id` | `other_id` |
| `outras` | `others` |
| `outros` | `others` |
| `pacientes` | `patients` |
| `pagamentos` | `payments` |
| `pagar` | `payable_total` |
| `pagas` | `paid_count` |
| `pago` | `paid` |
| `_pago` | `_paid` |
| `pago_anterior` | `paid_previous` |
| `pago_hoje` | `paid_today` |
| `pago_mes` | `paid_month` |
| `pagos` | `paid_payments` |
| `painel` | `panel` |
| `papeis_` | `roles_` |
| `para` | `redirect_to` |
| `parametro` | `parameter` |
| `parametros` | `parameters` |
| `parcelas` | `installments` |
| `parcelas_no_cartao` | `card_installments` |
| `parcelas_vencidas` | `overdue_installments` |
| `parte` | `part` |
| `partes` | `parts` |
| `passo` | `step` |
| `pedido` | `exam_order` |
| `pendente` | `pending_login` |
| `pendentes` | `pending` |
| `periodo` | `period` |
| `pesos_da_vez` | `weights` |
| `piso` | `floor` |
| `pode_alterar` | `can_change` |
| `pode_dar_desconto` | `can_give_discount` |
| `pode_desconto` | `can_discount` |
| `pode_fechar` | `can_close` |
| `pode_reabrir` | `can_reopen` |
| `pontos` | `points` |
| `por_categoria` | `by_category` |
| `por_forma` | `by_method` |
| `por_id` | `by_id` |
| `por_mes` | `by_month` |
| `por_mes_dia` | `by_month_day` |
| `por_transacao` | `by_transaction` |
| `precisa` | `needs` |
| `presenca` | `attendance` |
| `primeira` | `first` |
| `primeiro_vencimento` | `first_due_date` |
| `problema` | `problem` |
| `procurados` | `wanted` |
| `profissionais` | `practitioners` |
| `_profissional_do_prontuario` | `_record_practitioner` |
| `proibidos` | `forbidden` |
| `proprio` | `own` |
| `proprios` | `own_ones` |
| `protegida` | `protected` |
| `proximo` | `following` |
| `proximos` | `upcoming` |
| `quadrante` | `quadrant` |
| `quantos` | `how_many` |
| `quem` | `who` |
| `quem_enviou` | `sender` |
| `realizado` | `actual` |
| `realizado_total` | `actual_total` |
| `receber` | `receivable_total` |
| `recebido` | `received` |
| `recebido_anterior` | `received_previous` |
| `recebido_hoje` | `received_today` |
| `recebido_mes` | `received_month` |
| `recebidos` | `received_payments` |
| `rechamada` | `recall` |
| `rechamadas` | `recalls` |
| `RedirecionamentoPermanente` | `PermanentRedirect` |
| `redirecionar` | `redirect_old` |
| `reforcos` | `top_ups` |
| `registro_profissional` | `professional_registration` |
| `registros` | `records` |
| `registros_apagados` | `deleted_records` |
| `relacionada` | `related_person` |
| `relacionadas` | `related_people` |
| `relatorio` | `report` |
| `repeticoes` | `repetitions` |
| `repetida` | `repeated_one` |
| `repetido` | `repeated` |
| `restante` | `remaining` |
| `restantes` | `remaining_ones` |
| `resto` | `remainder` |
| `restricao` | `constraint` |
| `resultado` | `result` |
| `retiradas` | `withdrawals` |
| `_rotulo` | `_label` |
| `rotulos` | `labels` |
| `rotulos_das_formas` | `method_labels` |
| `saida` | `output` |
| `saidas` | `outflows` |
| `salario` | `salary` |
| `saldo` | `balance` |
| `saldo_bloco` | `balance_block` |
| `saldo_sistema` | `system_balance` |
| `saldo_texto` | `balance_text` |
| `saldos` | `balances` |
| `saude` | `health_old` |
| `secao` | `section` |
| `secoes` | `sections` |
| `segunda` | `second` |
| `segundos` | `seconds` |
| `selecionados` | `selected` |
| `sem_acento` | `unaccented` |
| `sem_acentos` | `unaccented` |
| `sem_agenda` | `no_schedule` |
| `sem_centro` | `no_cost_center` |
| `sem_grupo` | `ungrouped` |
| `semanas_antes` | `weeks_before` |
| `semanas_depois` | `weeks_after` |
| `semente` | `seed` |
| `senha_admin` | `admin_password` |
| `senha_financeiro` | `finance_password` |
| `senha_profissional` | `practitioner_password` |
| `senha_recepcao` | `front_desk_password` |
| `senhas` | `passwords` |
| `sinal` | `sign` |
| `so_digitos` | `all_digits` |
| `sobreposicao` | `overlap` |
| `soma` | `weighted_sum` |
| `somar` | `add_up` |
| `sorte` | `rng` / `roll` |
| `sorteado` | `drawn` |
| `sorteio` | `rng` |
| `stdnum_erros` | `stdnum_errors` |
| `tamanho_tabela` | `table_size` |
| `tamanhos` | `sizes` |
| `_telefone` | `_phone` |
| `telefones` | `phones` |
| `tem_historico` | `has_history` |
| `tentativas` | `attempts` |
| `termina` | `ends` |
| `termo` | `term` |
| `testar_volta` | `test_rollback` |
| `teto` | `ceiling` |
| `texto_do_dump` | `dump_text` |
| `tipo_antigo` | `old_kind` |
| `tipo_conferido` | `checked_kind` |
| `tipo_movimento` | `movement_kind` |
| `tipos` | `kinds` |
| `tipos_criados` | `kinds_created` |
| `titulo` | `title` |
| `topo` | `top` |
| `totais` | `totals` |
| `total_agendamentos` | `appointment_total` |
| `total_dias` | `total_days` |
| `total_pacientes` | `patient_total` |
| `total_pago` | `total_paid` |
| `total_recebido` | `total_received` |
| `total_rechamadas` | `recall_total` |
| `trabalhando` | `working` |
| `traducao` | `translated` |
| `transacao` | `bank_transaction` |
| `transacoes` | `transactions` |
| `tratamento` | `treatment` |
| `trecho` | `segment` |
| `trechos` | `segments` |
| `ufs_legado` | `legacy_states` |
| `ultimo_fim` | `last_end` |
| `unidade` | `unit` |
| `usados` | `used` |
| `usuarios` | `users` |
| `validar` | `validate` |
| `valor_paciente` | `patient_amount` |
| `valores` | `values` |
| `variante` | `variant` |
| `vencido` | `overdue` |
| `ver_rechamadas` | `can_see_recalls` |
| `versao` | `version_old` |
| `vieram` | `attended` |
| `vinculo` | `membership` |
| `vinculos` | `memberships` |
| `vistos` | `seen` |
| `vizinhos` | `neighbors` |

## Lo que queda en portugués

- **Valores guardados en la base**: los valores de las opciones (`"PF"`, `"conciliada"`, `"retirada"`), los códigos de los módulos (`"rechamadas"`), las claves dentro de campos JSON (los cambios de la auditoría, configuraciones). Solo cambia el nombre de las constantes (`Situacao.CONCILIADA` → `Status.RECONCILED`), no su valor.
- **Los labels de las apps** (`pacientes`, `financeiro`…), que dan nombre a las migraciones y a los tipos de contenido (ya a ninguna tabla).
- **Las migraciones antiguas**: describen el pasado, con los nombres de la época.
- **Los textos del importador del Odonto heredado**: son los nombres de las tablas y columnas del sistema antiguo.

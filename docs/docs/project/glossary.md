---
sidebar_position: 3.5
---

# Glossary of names

The code's names are moving from Portuguese to English (decisions 155 to 159); the screens stay in Portuguese, with translations. This page is the list both the people and the renaming tool follow: one English name for each Portuguese one, in the whole code.

## How a name is renamed

- **Only identifiers change**, read as Python tokens and template variables, never as text: the screens' texts, `_()` and `{% translate %}` stay as they are.
- **The database follows the code** (decision 179): a table is named `<app>_<model>` (`patients_patient`), a column after its field (`birth_date`), an index or constraint after what it does (`appointment_no_overlap`). Until decision 179 the renames kept the Portuguese tables and columns (`Meta.db_table`, `db_column`), so that the previous version still worked.
- **A rename never collides**: a file that already uses the new name for something else (a variable `date` beside a field `data`, `type` the built-in) is done by hand.
- **A field keeps its Portuguese label**: without `verbose_name` Django builds the label from the name, so a field renamed to English would show "created by" on the screens and in the audit. A renamed field states its label (`_("criado por")`); a test fails the run otherwise (decision 170).
- **The tests watch the templates**: a variable a template looks up and does not find fails the run, unless it is in `tests/missing_template_variables.txt` (decision 159). A rename keeps that list the same, with the new names.

## Models (done)

| Before | After | App label |
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

## Fields, first batch

The names that repeat across the models, in four parts. **Done:** `clinica`, `criado_em`/`criada_em`, `alterado_em`/`alterada_em` and `criado_por` (decision 160), `paciente`, `profissional` and `usuario` (decision 161), `nome`, `ativo`/`ativa`, `codigo`, `descricao`, `observacoes`, `observacao`, `telefone` and `numero` (decision 163), `tipo`, `valor`, `situacao`, `atendimento` and `lancamento` (decision 164), `data` and `conta` (decision 165), the 19 names after `conta` in the table (decision 166; local variables with these exact names too, such as `clinica` → `clinic`). Then each app's own fields, and last the functions and variables.

| Before | After |
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

## Fields of each app

Each app's own fields, one app at a time. **Done:** finance (decision 167), patients (decision 168), core and medical records (decision 169), and the other nine apps (decision 171): every model field now has an English name.

### Finance (`financeiro`)

| Before | After |
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

### Patients (`pacientes`)

| Before | After |
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

`rg` stays: it is the Brazilian document's name, like `cpf`.

### Core (`core`)

| Before | After |
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

`area` is already English.

### Medical records (`prontuario`)

| Before | After |
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

### Staff (`pessoal`)

| Before | After |
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

### Estimates (`orcamentos`)

| Before | After |
|---|---|
| `decidido_em` | `decided_at` |
| `decidido_por` | `decided_by` |
| `orcamento` | `estimate` |
| `procedimento` | `procedure` |
| `dentes` | `teeth` |
| `quantidade` | `quantity` |
| `valor_unitario` | `unit_price` |

### Audit (`auditoria`)

| Before | After |
|---|---|
| `usuario_nome` | `user_name` |
| `acao` | `action` |
| `modelo` | `model_name` |
| `objeto_id` | `object_id` |
| `objeto_descricao` | `object_repr` |
| `alteracoes` | `changes` |

### Account (two-step login) (`conta`)

| Before | After |
|---|---|
| `segredo` | `secret` |
| `ativada_em` | `activated_at` |
| `ultimo_passo` | `last_step` |
| `resumo` | `digest` |
| `usado_em` | `used_at` |

### Health plans (`convenios`)

| Before | After |
|---|---|
| `convenio` | `health_plan` |
| `plano` | `plan` |
| `beneficiario` | `member_code` |
| `titular` | `holder` |

### Reference data (`referencias`)

| Before | After |
|---|---|
| `sigla` | `abbreviation` |
| `regiao` | `region` |
| `nome_curto` | `short_name` |
| `ordem` | `sort_order` |

### Practitioners (`profissionais`)

| Before | After |
|---|---|
| `comissao_percentual` | `commission_percentage` |

### Recalls (`rechamadas`)

| Before | After |
|---|---|
| `concluida` | `done` |

### Schedule (`agenda`)

| Before | After |
|---|---|
| `serie` | `series` |

## Functions and variables

The last part of the plan (decision 159): the functions, methods, classes, constants and variables. **Only Python names change** here: the strings stay, so do the templates' context keys, the query names, the JSON keys and the stored values, which a variable's name only happens to match. A form's declared fields keep their names (they are the posted names); the names a URL passes to its view and a test's `parametrize` names follow the function's parameters. **Done:** the variables shared by many apps (decision 172), the core app (decision 173), finance (decision 174), schedule (decision 175), patients, medical records, estimates, staff, recalls, health plans, practitioners and team (decision 176), legacy, audit, account, help, dentistry, monitoring and reference data (decision 177), and the releases (decision 178): every app's Python names are in English.

### Shared variables

| Before | After |
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

`itens` stays for now: it is also the estimate's reverse accessor and the releases' format.

### Core (`core`): classes

| Before | After |
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

### Core: enum members

| Before | After |
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

### Core: constants

| Before | After |
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

### Core: functions and methods

| Before | After |
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

`Usuario` (the user model) keeps its name for now (see below).

### Schedule (`agenda`)

| Before | After |
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

### Patients, medical records, estimates, staff, recalls, health plans, practitioners, team

| Before | After |
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

Each app's views (renamed only inside the app, the same old name meaning a different view in each):

`patients`:

| Before | After |
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

| Before | After |
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

| Before | After |
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

| Before | After |
|---|---|
| `lancar` | `post_payroll` |
| `results` | `employee_list` |
| `new` | `new_employee` |
| `editar` | `edit_employee` |
| `_formulario` | `_employee_form` |
| `folha` | `payroll` |

`recalls`:

| Before | After |
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

| Before | After |
|---|---|
| `results` | `health_plan_list` |
| `new` | `new_health_plan` |
| `editar` | `edit_health_plan` |
| `_convenio` | `_health_plan_form` |

`practitioners`:

| Before | After |
|---|---|
| `results` | `practitioner_list` |
| `new` | `new_practitioner` |
| `editar` | `edit_practitioner` |
| `_formulario` | `_practitioner_form` |
| `excluir` | `delete_practitioner` |

`team`:

| Before | After |
|---|---|
| `results` | `member_list` |
| `new` | `new_member` |
| `editar` | `edit_member` |

### Legacy, audit, account, help, dentistry, monitoring, reference data

| Before | After |
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

Renamed only inside their app (common words):

`legacy`:

| Before | After |
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

| Before | After |
|---|---|
| `results` | `audit_list` |
| `_data` | `_date` |
| `_valor` | `_value` |
| `_valores` | `_values` |

`monitoring`:

| Before | After |
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

| Before | After |
|---|---|
| `verificar` | `verify` |
| `ativar` | `activate` |
| `desativar` | `deactivate` |
| `recuperar` | `password_recover` |

`help`:

| Before | After |
|---|---|
| `privacidade` | `privacy` |

`reference_data`:

| Before | After |
|---|---|
| `cidades` | `cities` |
| `bancos` | `banks` |

### Releases (`novidades`)

| Before | After |
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

The public interface keeps its names: the API's fields (`versao`, `data`, `titulo`, `itens`, `tipo`, `tipo_nome`, `modulo`, `texto`, `origem`, `pr`) and query names (`publico`, `desde`), and the keys of `releases.yaml`, which the release's attributes and the page mirror.

### Finance (`financeiro`): classes

| Before | After |
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

### Finance: enum classes and members

| Before | After |
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

### Finance: constants

| Before | After |
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

### Finance: functions, methods and views

| Before | After |
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

The enum classes `Tipo`, `Situacao` and `Forma` of every app became `Kind`, `Status` and `Method`, as their fields `kind`, `status`, `method`; the members of other apps follow with their app.

## Settings, CSS classes and HTML hooks (done)

The settings of `config/settings.py` and the names the templates, the stylesheet and the scripts share (decision 182). A class built from a stored value keeps the value: `status-compareceu`, `kind-novo`. The ids of filter fields named after their query (`de`, `agrupar`) followed it in decision 184 (`since`, `group`).

### Settings

| Before | After |
|---|---|
| `NOME_SISTEMA` | `SYSTEM_NAME` |
| `RELEASES_ARQUIVO` | `RELEASES_FILE` |
| `INATIVIDADE_MINUTOS` | `IDLE_MINUTES` |
| `RECUPERAR_SENHA_POR_EMAIL` | `PASSWORD_RECOVERY_BY_EMAIL` |
| `env_renomeada` | `env_renamed` |
| `env_lista` | `env_list` |

### CSS classes

| Before | After |
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

### HTML ids

| Before | After |
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

### data- attributes

| Before | After |
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

## Script names (done)

The local variables and functions of the scripts in `static/js` (`evento` → `event`, `campo` → `field`, `abrirModal` → `openModal`) and the names the schedule page's script shares with the server (decision 183). The stored values the scripts compare stay as they are (`"desmarcou"`, `"agendado"`).

### Schedule settings (`schedule-settings`)

| Before | After |
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

### Event, storage and badges

| Before | After | Where |
|---|---|---|
| `agendaAtualizada` | `scheduleUpdated` | HTMX event the server sends after a save (`HX-Trigger`) |
| `mensagem` | `message` | its text |
| `kaladrius-atividade` | `kaladrius-activity` | `localStorage` key of the last activity |
| `aniversariantes` | `birthday-badge` | class of the birthdays badge |
| `rechamadas` | `recall-badge` | class of the recalls badge |

## Form fields and query names (done)

The fields of forms that are not a model's field, the names the pages send in the address or in a form (`?de=` → `?since=`, `name="acao"` → `name="action"`) and the prefixes of the two-step verification forms (decision 184). Their values stay: `?group=mes`, `action=finalizar`, `scope=serie`, like the stored values. An address from before decision 155 is redirected with the old query names translated (`/financeiro/fluxo-de-caixa/?de=…&agrupar=mes` → `/finance/cash-flow/?since=…&group=mes`).

### Form fields

| Before | After |
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

### Query and form names

| Before | After |
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

### Form prefixes

| Before | After |
|---|---|
| `desativar` | `disable` |
| `codigos` | `codes` |

## Template context names (done)

The names the views and context processors give the templates, and the templates' own variables (`{% for %}`, `{% with %}`, `as`), in all templates (decision 185): `{{ nome_sistema }}` → `{{ system_name }}`, `pode.agenda.ver` → `can.agenda.ver`, `pagina` → `page`. Kept: the keys inside a value (`dashboard.rechamadas`, and the module and action codes in `can.agenda.ver`), the placeholders inside `{% blocktranslate %}`, which are part of the translated text; when one came from a renamed name the tag binds it (`{% blocktranslate with versao_sistema=system_version %}`). The block `titulo` became `title` in decision 187.

| Before | After |
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

## Keys inside the values (done)

The keys of the dictionaries the services and views build for the pages (the home summary, the cash flow, the reports, the planning, the commissions, the cash register, the debtors, the server health), the attributes the views add to objects, and the fields of the legislation table (decision 186): `dashboard.rechamadas` → `dashboard.recalls`, `row.vencido` → `row.overdue`, `law.curta` → `law.short_name`. The server health uses the names `health.sh` writes (`time`, `memory_total`…); lines of the old format, with Portuguese names, are still read. Kept: the module and action codes (`can.agenda.ver`), the document roles (`country_documents.paciente`), the fields of the release notes (they are the `releases.yaml` format and the `/api/v1/releases` API), the models' `related_name`s (`estimate.itens`), and the placeholders of translated texts (`%(anos)s`).

### Dictionary keys

| Before | After |
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

### Attributes added by the views

| Before | After |
|---|---|
| `comissao_devolvida` | `commission_returned` |
| `lista_pagamentos` | `payment_list` |
| `pacientes` (`health_plan`)` | `patient_count` |
| `pago` | `paid` |
| `pendentes` | `pending` |
| `salario_atual` | `current_salary` |

### Legislation

| Before | After |
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

## Test fixtures and variables (done)

The Python names the tests define (decision 188): the fixtures, the helpers, their parameters, the local variables, the constants and the keys of the `scenario` dictionaries, about 450 names in 62 files. The fictitious data stays in Portuguese, like the screens (`"Maria Paciente"`, `"Clínica fictícia"`, the users `recepcao` and `admin`), and so do the names a test reads from the system's own objects (`release.versao`, `entry.parcelas`). The shared ones:

| Before | After |
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

### Keys of `scenario`

| Before | After |
|---|---|
| `agenda` | `schedule` |
| `canal` | `channel` |
| `cliente` | `client` |
| `despesa` | `expense` |
| `receita` | `income` |
| `recepcao` | `reception` |
| `tratamento` | `treatment` |

## What stays in Portuguese

- **Values stored in the database**: the choices' values (`"PF"`, `"conciliada"`, `"retirada"`), module codes (`"rechamadas"`), the keys inside JSON fields (the audit's changes, settings). Only the constants' names change (`Situacao.CONCILIADA` → `Status.RECONCILED`), not their value.
- **The app labels** (`pacientes`, `financeiro`…), which name the migrations and content types (no longer any table).
- **The old migrations**: they describe the past, with the names of the time.
- **The legacy Odonto importer's strings**: they are the old system's table and column names.

---
sidebar_position: 3.5
---

# Glosario de nombres

Los nombres del código están pasando del portugués al inglés (decisiones 155 a 159); las pantallas siguen en portugués, con traducciones. Esta página es la lista que siguen las personas y la herramienta de renombrado: un nombre en inglés para cada nombre en portugués, en todo el código.

## Cómo se renombra un nombre

- **Solo cambian identificadores**, leídos como tokens de Python y variables de plantilla, nunca como texto: los textos de las pantallas, los `_()` y los `{% translate %}` quedan como están.
- **La base mantiene sus nombres**: el modelo mantiene su tabla (`Meta.db_table`), el campo su columna (`db_column`). Las migraciones no ejecutan SQL, y la versión anterior (la vuelta automática) sigue funcionando.
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

La última parte del plan (decisión 159): las funciones, métodos, clases, constantes y variables. **Aquí solo cambian nombres de Python**: las cadenas quedan, y con ellas las claves de contexto de las plantillas, los nombres de consulta, las claves de JSON y los valores guardados, con los que el nombre de una variable solo coincide. Los campos declarados de un formulario mantienen su nombre (son los nombres enviados), y los nombres que una URL pasa a la vista y el `parametrize` de una prueba siguen a los parámetros de la función. **Hecho:** las variables comunes a varias apps (decisión 172), la app core (decisión 173).

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

## Lo que queda en portugués

- **Valores guardados en la base**: los valores de las opciones (`"PF"`, `"conciliada"`, `"retirada"`), los códigos de los módulos (`"rechamadas"`), las claves dentro de campos JSON (los cambios de la auditoría, configuraciones). Solo cambia el nombre de las constantes (`Situacao.CONCILIADA` → `Status.RECONCILED`), no su valor.
- **Nombres de tablas y columnas**, y los labels de las apps (`pacientes`, `financeiro`…), que dan nombre a las tablas y migraciones.
- **Las migraciones antiguas**: describen el pasado, con los nombres de la época.
- **Los textos del importador del Odonto heredado**: son los nombres de las tablas y columnas del sistema antiguo.
- **`Usuario`**, el modelo de usuario (`AUTH_USER_MODEL`), por ahora: pide un plan propio.

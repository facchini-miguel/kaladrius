---
sidebar_position: 3.5
---

# Glossário de nomes

Os nomes do código estão passando do português para o inglês (decisões 155 a 159); as telas continuam em português, com traduções. Esta página é a lista que as pessoas e a ferramenta de renomeação seguem: um nome em inglês para cada nome em português, no código todo.

## Como um nome é renomeado

- **Só mudam identificadores**, lidos como tokens do Python e variáveis de template, nunca como texto: os textos das telas, os `_()` e os `{% translate %}` ficam como estão.
- **O banco mantém seus nomes**: o modelo mantém a tabela (`Meta.db_table`), o campo a coluna (`db_column`). As migrações não rodam SQL, e a versão anterior (a volta automática) continua funcionando.
- **Uma renomeação nunca colide**: um arquivo que já usa o nome novo para outra coisa (uma variável `date` ao lado de um campo `data`, o `type` do Python) é feito à mão.
- **Um campo mantém o rótulo em português**: sem `verbose_name` o Django monta o rótulo a partir do nome, então um campo renomeado para inglês mostraria "created by" nas telas e na auditoria. Um campo renomeado diz o próprio rótulo (`_("criado por")`); senão um teste falha (decisão 170).
- **Os testes vigiam os templates**: uma variável que um template procura e não acha faz a rodada falhar, a menos que esteja em `tests/missing_template_variables.txt` (decisão 159). Uma renomeação mantém essa lista igual, com os nomes novos.

## Modelos (feito)

| Antes | Depois | Label do app |
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

## Campos, primeiro lote

Os nomes que se repetem entre os modelos, em quatro partes. **Feito:** `clinica`, `criado_em`/`criada_em`, `alterado_em`/`alterada_em` e `criado_por` (decisão 160), `paciente`, `profissional` e `usuario` (decisão 161), `nome`, `ativo`/`ativa`, `codigo`, `descricao`, `observacoes`, `observacao`, `telefone` e `numero` (decisão 163), `tipo`, `valor`, `situacao`, `atendimento` e `lancamento` (decisão 164), `data` e `conta` (decisão 165), os 19 nomes depois de `conta` na tabela (decisão 166; também as variáveis locais com esses nomes exatos, como `clinica` → `clinic`). Depois, os campos próprios de cada app e, por último, as funções e variáveis.

| Antes | Depois |
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

Os campos próprios de cada app, um app por vez. **Feito:** financeiro (decisão 167), pacientes (decisão 168), core e prontuário (decisão 169), e os outros nove apps (decisão 171): todo campo de modelo agora tem nome em inglês.

### Financeiro (`financeiro`)

| Antes | Depois |
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

| Antes | Depois |
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

`rg` fica: é o nome do documento brasileiro, como `cpf`.

### Core (`core`)

| Antes | Depois |
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

`area` já é inglês.

### Prontuário (`prontuario`)

| Antes | Depois |
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

### Pessoal (`pessoal`)

| Antes | Depois |
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

### Orçamentos (`orcamentos`)

| Antes | Depois |
|---|---|
| `decidido_em` | `decided_at` |
| `decidido_por` | `decided_by` |
| `orcamento` | `estimate` |
| `procedimento` | `procedure` |
| `dentes` | `teeth` |
| `quantidade` | `quantity` |
| `valor_unitario` | `unit_price` |

### Auditoria (`auditoria`)

| Antes | Depois |
|---|---|
| `usuario_nome` | `user_name` |
| `acao` | `action` |
| `modelo` | `model_name` |
| `objeto_id` | `object_id` |
| `objeto_descricao` | `object_repr` |
| `alteracoes` | `changes` |

### Conta (login em duas etapas) (`conta`)

| Antes | Depois |
|---|---|
| `segredo` | `secret` |
| `ativada_em` | `activated_at` |
| `ultimo_passo` | `last_step` |
| `resumo` | `digest` |
| `usado_em` | `used_at` |

### Convênios (`convenios`)

| Antes | Depois |
|---|---|
| `convenio` | `health_plan` |
| `plano` | `plan` |
| `beneficiario` | `member_code` |
| `titular` | `holder` |

### Referências (`referencias`)

| Antes | Depois |
|---|---|
| `sigla` | `abbreviation` |
| `regiao` | `region` |
| `nome_curto` | `short_name` |
| `ordem` | `sort_order` |

### Profissionais (`profissionais`)

| Antes | Depois |
|---|---|
| `comissao_percentual` | `commission_percentage` |

### Rechamadas (`rechamadas`)

| Antes | Depois |
|---|---|
| `concluida` | `done` |

### Agenda (`agenda`)

| Antes | Depois |
|---|---|
| `serie` | `series` |

## Funções e variáveis

A última parte do plano (decisão 159): as funções, métodos, classes, constantes e variáveis. **Aqui só mudam nomes do Python**: as strings ficam, e com elas as chaves de contexto dos templates, os nomes de consulta, as chaves de JSON e os valores gravados, com que o nome de uma variável só coincide. Os campos declarados de um formulário mantêm o nome (são os nomes postados), e os nomes que uma URL passa para a view e o `parametrize` de um teste acompanham os parâmetros da função. **Feito:** as variáveis comuns a vários apps (decisão 172), o app core (decisão 173), financeiro (decisão 174), agenda (decisão 175), pacientes, prontuário, orçamentos, pessoal, rechamadas, convênios, profissionais e equipe (decisão 176).

### Variáveis comuns

| Antes | Depois |
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

`itens` fica por enquanto: também é o acesso reverso do orçamento e o formato das releases.

### Core (`core`): classes

| Antes | Depois |
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

### Core: membros dos enums

| Antes | Depois |
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

| Antes | Depois |
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

### Core: funções e métodos

| Antes | Depois |
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

`Usuario` (o modelo de usuário) mantém o nome por enquanto (veja abaixo).

### Agenda (`agenda`)

| Antes | Depois |
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

### Pacientes, prontuário, orçamentos, pessoal, rechamadas, convênios, profissionais, equipe

| Antes | Depois |
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

As views de cada app (renomeadas só dentro do app, pois o mesmo nome antigo era uma view diferente em cada um):

`patients`:

| Antes | Depois |
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

| Antes | Depois |
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

| Antes | Depois |
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

| Antes | Depois |
|---|---|
| `lancar` | `post_payroll` |
| `results` | `employee_list` |
| `new` | `new_employee` |
| `editar` | `edit_employee` |
| `_formulario` | `_employee_form` |
| `folha` | `payroll` |

`recalls`:

| Antes | Depois |
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

| Antes | Depois |
|---|---|
| `results` | `health_plan_list` |
| `new` | `new_health_plan` |
| `editar` | `edit_health_plan` |
| `_convenio` | `_health_plan_form` |

`practitioners`:

| Antes | Depois |
|---|---|
| `results` | `practitioner_list` |
| `new` | `new_practitioner` |
| `editar` | `edit_practitioner` |
| `_formulario` | `_practitioner_form` |
| `excluir` | `delete_practitioner` |

`team`:

| Antes | Depois |
|---|---|
| `results` | `member_list` |
| `new` | `new_member` |
| `editar` | `edit_member` |

### Financeiro (`financeiro`): classes

| Antes | Depois |
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

### Financeiro: classes e membros dos enums

| Antes | Depois |
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

### Financeiro: constantes

| Antes | Depois |
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

### Financeiro: funções, métodos e views

| Antes | Depois |
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

As classes de enum `Tipo`, `Situacao` e `Forma` de todos os apps viraram `Kind`, `Status` e `Method`, como os campos `kind`, `status`, `method`; os membros dos outros apps seguem com o app deles.

## O que fica em português

- **Valores gravados no banco**: os valores das escolhas (`"PF"`, `"conciliada"`, `"retirada"`), os códigos dos módulos (`"rechamadas"`), as chaves dentro de campos JSON (as alterações da auditoria, configurações). Só muda o nome das constantes (`Situacao.CONCILIADA` → `Status.RECONCILED`), não o valor.
- **Nomes de tabelas e colunas**, e os labels dos apps (`pacientes`, `financeiro`…), que dão nome às tabelas e migrações.
- **As migrações antigas**: descrevem o passado, com os nomes da época.
- **Os textos do importador do Odonto legado**: são os nomes das tabelas e colunas do sistema antigo.
- **`Usuario`**, o modelo de usuário (`AUTH_USER_MODEL`), por enquanto: pede um plano próprio.

---
sidebar_position: 3.5
---

# Glossary of names

The code's names are moving from Portuguese to English (decisions 155 to 159); the screens stay in Portuguese, with translations. This page is the list both the people and the renaming tool follow: one English name for each Portuguese one, in the whole code.

## How a name is renamed

- **Only identifiers change**, read as Python tokens and template variables, never as text: the screens' texts, `_()` and `{% translate %}` stay as they are.
- **The database keeps its names**: a model keeps its table (`Meta.db_table`), a field its column (`db_column`). The migrations run no SQL, and the previous version (the automatic rollback) still works.
- **A rename never collides**: a file that already uses the new name for something else (a variable `date` beside a field `data`, `type` the built-in) is done by hand.
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

Each app's own fields, one app at a time. **Done:** finance (decision 167), patients (decision 168), core and medical records (decision 169).

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

## What stays in Portuguese

- **Values stored in the database**: the choices' values (`"PF"`, `"conciliada"`, `"retirada"`), module codes (`"rechamadas"`), the keys inside JSON fields (the audit's changes, settings). Only the constants' names change (`Situacao.CONCILIADA` → `Status.RECONCILED`), not their value.
- **Table and column names**, and the app labels (`pacientes`, `financeiro`…), which name the tables and migrations.
- **The old migrations**: they describe the past, with the names of the time.
- **The legacy Odonto importer's strings**: they are the old system's table and column names.
- **`Usuario`**, the user model (`AUTH_USER_MODEL`), for now: it needs a plan of its own.

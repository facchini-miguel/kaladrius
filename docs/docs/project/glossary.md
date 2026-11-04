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

The names that repeat across the models. Then each app's own fields, and last the functions and variables.

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

## What stays in Portuguese

- **Values stored in the database**: the choices' values (`"PF"`, `"conciliada"`, `"retirada"`), module codes (`"rechamadas"`), the keys inside JSON fields (the audit's changes, settings). Only the constants' names change (`Situacao.CONCILIADA` → `Status.RECONCILED`), not their value.
- **Table and column names**, and the app labels (`pacientes`, `financeiro`…), which name the tables and migrations.
- **The old migrations**: they describe the past, with the names of the time.
- **The legacy Odonto importer's strings**: they are the old system's table and column names.
- **`Usuario`**, the user model (`AUTH_USER_MODEL`), for now: it needs a plan of its own.

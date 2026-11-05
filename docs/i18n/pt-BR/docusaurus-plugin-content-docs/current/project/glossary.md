---
sidebar_position: 3.5
---

# Glossário de nomes

Os nomes do código estão passando do português para o inglês (decisões 155 a 159); as telas continuam em português, com traduções. Esta página é a lista que as pessoas e a ferramenta de renomeação seguem: um nome em inglês para cada nome em português, no código todo.

## Como um nome é renomeado

- **Só mudam identificadores**, lidos como tokens do Python e variáveis de template, nunca como texto: os textos das telas, os `_()` e os `{% translate %}` ficam como estão.
- **O banco mantém seus nomes**: o modelo mantém a tabela (`Meta.db_table`), o campo a coluna (`db_column`). As migrações não rodam SQL, e a versão anterior (a volta automática) continua funcionando.
- **Uma renomeação nunca colide**: um arquivo que já usa o nome novo para outra coisa (uma variável `date` ao lado de um campo `data`, o `type` do Python) é feito à mão.
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

Os campos próprios de cada app, um app por vez. **Feito:** financeiro (decisão 167), pacientes (decisão 168), core e prontuário (decisão 169).

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

## O que fica em português

- **Valores gravados no banco**: os valores das escolhas (`"PF"`, `"conciliada"`, `"retirada"`), os códigos dos módulos (`"rechamadas"`), as chaves dentro de campos JSON (as alterações da auditoria, configurações). Só muda o nome das constantes (`Situacao.CONCILIADA` → `Status.RECONCILED`), não o valor.
- **Nomes de tabelas e colunas**, e os labels dos apps (`pacientes`, `financeiro`…), que dão nome às tabelas e migrações.
- **As migrações antigas**: descrevem o passado, com os nomes da época.
- **Os textos do importador do Odonto legado**: são os nomes das tabelas e colunas do sistema antigo.
- **`Usuario`**, o modelo de usuário (`AUTH_USER_MODEL`), por enquanto: pede um plano próprio.

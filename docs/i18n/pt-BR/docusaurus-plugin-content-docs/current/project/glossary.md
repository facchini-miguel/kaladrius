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

Os nomes que se repetem entre os modelos, em quatro partes. **Feito:** `clinica`, `criado_em`/`criada_em`, `alterado_em`/`alterada_em` e `criado_por` (decisão 160), `paciente`, `profissional` e `usuario` (decisão 161), `nome`, `ativo`/`ativa`, `codigo`, `descricao`, `observacoes`, `observacao`, `telefone` e `numero` (decisão 163; também as variáveis locais com esses nomes exatos, como `clinica` → `clinic`). Depois, os campos próprios de cada app e, por último, as funções e variáveis.

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

## O que fica em português

- **Valores gravados no banco**: os valores das escolhas (`"PF"`, `"conciliada"`, `"retirada"`), os códigos dos módulos (`"rechamadas"`), as chaves dentro de campos JSON (as alterações da auditoria, configurações). Só muda o nome das constantes (`Situacao.CONCILIADA` → `Status.RECONCILED`), não o valor.
- **Nomes de tabelas e colunas**, e os labels dos apps (`pacientes`, `financeiro`…), que dão nome às tabelas e migrações.
- **As migrações antigas**: descrevem o passado, com os nomes da época.
- **Os textos do importador do Odonto legado**: são os nomes das tabelas e colunas do sistema antigo.
- **`Usuario`**, o modelo de usuário (`AUTH_USER_MODEL`), por enquanto: pede um plano próprio.

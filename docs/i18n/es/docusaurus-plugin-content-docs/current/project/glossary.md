---
sidebar_position: 3.5
---

# Glosario de nombres

Los nombres del código están pasando del portugués al inglés (decisiones 155 a 159); las pantallas siguen en portugués, con traducciones. Esta página es la lista que siguen las personas y la herramienta de renombrado: un nombre en inglés para cada nombre en portugués, en todo el código.

## Cómo se renombra un nombre

- **Solo cambian identificadores**, leídos como tokens de Python y variables de plantilla, nunca como texto: los textos de las pantallas, los `_()` y los `{% translate %}` quedan como están.
- **La base mantiene sus nombres**: el modelo mantiene su tabla (`Meta.db_table`), el campo su columna (`db_column`). Las migraciones no ejecutan SQL, y la versión anterior (la vuelta automática) sigue funcionando.
- **Un renombrado nunca choca**: un archivo que ya usa el nombre nuevo para otra cosa (una variable `date` junto a un campo `data`, el `type` de Python) se hace a mano.
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

Los nombres que se repiten entre los modelos, en cuatro partes. **Hecho:** `clinica`, `criado_em`/`criada_em`, `alterado_em`/`alterada_em` y `criado_por` (decisión 160), `paciente`, `profissional` y `usuario` (decisión 161; también las variables locales con esos nombres exactos, como `clinica` → `clinic`). Después, los campos propios de cada app y, por último, las funciones y variables.

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

## Lo que queda en portugués

- **Valores guardados en la base**: los valores de las opciones (`"PF"`, `"conciliada"`, `"retirada"`), los códigos de los módulos (`"rechamadas"`), las claves dentro de campos JSON (los cambios de la auditoría, configuraciones). Solo cambia el nombre de las constantes (`Situacao.CONCILIADA` → `Status.RECONCILED`), no su valor.
- **Nombres de tablas y columnas**, y los labels de las apps (`pacientes`, `financeiro`…), que dan nombre a las tablas y migraciones.
- **Las migraciones antiguas**: describen el pasado, con los nombres de la época.
- **Los textos del importador del Odonto heredado**: son los nombres de las tablas y columnas del sistema antiguo.
- **`Usuario`**, el modelo de usuario (`AUTH_USER_MODEL`), por ahora: pide un plan propio.

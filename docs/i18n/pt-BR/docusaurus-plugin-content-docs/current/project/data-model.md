---
sidebar_position: 3
---

# Modelo de dados

## Princípio multi-clínica
- Toda informação de uma clínica tem uma chave `clinica`. Nenhuma consulta é feita sem filtrar pela clínica atual.
- O filtro é aplicado de forma centralizada (middleware + managers), não manualmente em cada tela.
- **Falha fechada:** todo modelo da clínica herda de `ModeloDaClinica` (`apps/core/isolamento.py`). O gerenciador padrão filtra pela clínica atual e, se não houver clínica definida, **dá erro em vez de mostrar dados**. O filtro é decidido **quando a consulta é executada** (não quando é montada), o que permite declarar campos de formulário com dados da clínica. Gravar ou excluir um registro de outra clínica também dá erro. Código da plataforma que precisa ver todas as clínicas (admin do Django, comandos) usa `sem_isolamento()` explicitamente.
- A clínica atual vem da sessão e só é aceita se o usuário tiver vínculo ativo com ela (ou for superusuário). O admin do Django é restrito aos superusuários da plataforma.
- Tabelas de referência públicas (UF, cidade, banco, estado civil) são **globais**, compartilhadas entre as clínicas.

## Entidades

### Plataforma
| Entidade | Campos principais | Observação |
|---|---|---|
| `Clinica` | nome, documento (CPF/CNPJ), contato, ativa, configurações da agenda (início, fim, duração do slot) | O "tenant" |
| `Usuario` | login, nome, e-mail, senha (Argon2), ativo, idioma | Usuário do Django |
| `Vinculo` | usuario, clinica, papel, ativo | Um usuário pode atuar em mais de uma clínica |

### Papéis e permissões (substitui `sist_pessoasgrupos` / `sist_modulosperm`)
| Papel | Equivale no sistema antigo | Acesso padrão |
|---|---|---|
| Superusuário da plataforma | MASTER | Tudo, em todas as clínicas |
| Administrador da clínica | ADMINISTRADOR | Tudo dentro da própria clínica |
| Recepção | — | Agenda, pacientes, rechamadas, aniversariantes |
| Profissional | — | Agenda e pacientes. Vê e altera **só a própria agenda**: a do cadastro de profissional ligado ao seu usuário em Cadastros > Profissionais (decisão 044). Sem cadastro ligado, a agenda fica vazia, com um aviso |

Cada papel recebe as permissões `ver`, `criar`, `alterar` e `excluir` por módulo. A matriz fica em `apps/core/permissoes.py` e vale tanto no servidor (a requisição é bloqueada) quanto na tela (botões e menus somem). A revisão detalhada fica para depois da fase 1, como combinado.

| Módulo | Administrador | Recepção | Profissional |
|---|---|---|---|
| Pacientes | tudo | ver, criar, alterar | ver, criar, alterar |
| Agenda | tudo | tudo | ver, criar, alterar |
| Rechamadas | tudo | tudo | ver, criar, alterar |
| Aniversariantes | tudo | ver | ver |
| Profissionais | tudo | ver | ver |
| Tabelas base | tudo | ver | ver |
| Usuários da clínica | tudo | — | — |
| Configurações da clínica | tudo | — | — |
| Auditoria | ver | — | — |
| Recebimentos (a receber, receber, recibo, devedores) | tudo | ver, criar, alterar | — |
| Financeiro (categorias, contas; a pagar e fluxo de caixa na 0.16) | tudo | — | — |
| Orçamentos (aprovar exige também Recebimentos) | tudo | ver, criar, alterar | ver, criar, alterar |

O módulo "Usuários da clínica" é a tela **Cadastros > Equipe** (versão 0.8.0): o administrador cria contas já vinculadas à clínica, muda o perfil, define senhas e tira o acesso (o vínculo fica inativo; contas nunca são excluídas, por causa da auditoria). Ninguém altera o próprio perfil, e a clínica nunca fica sem um administrador ativo. Nome, e-mail e senha só podem ser alterados quando a conta é usada **somente** nesta clínica e não é de superusuário: assim, uma clínica não consegue tomar o acesso de alguém às outras. "Configurações da clínica" é a tela **Cadastros > Configurações da clínica** (versão 0.10.0): nome, CPF/CNPJ, e-mail, telefone, horário e intervalo da agenda. Uma mudança de horário ou intervalo que deixaria algum agendamento **futuro** fora da grade ou fora do intervalo é recusada, e a tela mostra qual (o histórico pode ter outros horários).

### Clínica
| Entidade | Campos principais | Sistema antigo |
|---|---|---|
| `Paciente` | clinica, tipo (PF/PJ), nome, razão social, CPF/CNPJ, RG, inscrição estadual, sexo, estado civil, nascimento, profissão, responsável, telefones (residencial, comercial, celular), WhatsApp, e-mail, endereço (CEP, UF, cidade, bairro, logradouro, número, complemento), observações, ativo, arquivado (com data e quem arquivou), datas de criação e alteração | `pessoas` |
| `Profissional` | clinica, nome, registro profissional (CRO/CRM…), cor, comissão (%, desde a 0.19), ativo, usuario (opcional) | `dentistas` |
| `TipoAtendimento` | clinica, nome, cor, ativo | `agenda_cor` (Cirurgia, Prótese…) |
| `Agendamento` | clinica, profissional, tipo, início e fim (data e hora), paciente (opcional), descrição, situação (agendado, compareceu, faltou, desmarcou; desde a 0.24), série (repetição), criado por | `agendax` |
| `Rechamada` | clinica, paciente, data, descrição, concluída, criado por | `agenda` (is_rechamada) |

### Referência (globais)
`UF`, `Cidade` (fonte: IBGE), `Banco` (fonte: lista pública do Banco Central), `EstadoCivil`.

### Financeiro (versão 0.15.0)
| Entidade | Campos principais | Observação |
|---|---|---|
| `Conta` | clinica, nome, tipo (dinheiro, banco, maquininha), saldo inicial (0.16.0), ativa | Onde o dinheiro entra. Toda clínica começa com Caixa e Banco |
| `Categoria` | clinica, nome, tipo (receita, despesa), ativa | Toda clínica começa com 3 de receita e 8 de despesa; o administrador cadastra outras |
| `Lancamento` | clinica, tipo (a receber, a pagar), descrição, categoria, paciente (opcional) ou pagador em texto, profissional (opcional), valor total, data, observações, cancelado (com motivo, quando e quem), criado por | Nunca é excluído: é cancelado |
| `Parcela` | clinica, lançamento, número, vencimento, valor | O pago e o saldo são calculados a partir dos pagamentos |
| `Pagamento` | clinica, parcela, data, valor recebido, juros e multa (incluídos no valor), desconto (só administrador), forma (dinheiro, Pix, débito, crédito, transferência, boleto, cheque), conta, bandeira, parcelas e código da transação do cartão, observação, estornado (com motivo, quando e quem), recebido por | Abate da parcela: valor − juros + desconto. Nunca guarda o número do cartão |

| `Caixa` | clinica, conta, aberto em/por, valor contado na abertura, fechado em/por, valor esperado e contado no fechamento, observação | Caixa do dia (0.17.0). Um aberto por conta; o esperado é gravado ao fechar, para estornos posteriores não mudarem um caixa fechado |
| `MovimentoCaixa` | clinica, caixa, tipo (retirada, reforço), valor, outra conta (opcional), motivo, criado por | Retirada para outra conta (depósito no banco) move o saldo entre as contas; sem outra conta, o dinheiro sai ou entra no sistema e aparece no fluxo de caixa |
| `Comissao` | clinica, profissional, recebimentos até, percentual, valor recebido, comissão de estornos descontada, valor, lançamento a pagar, cancelada, criado por | Desde a 0.19. Os pagamentos cobertos apontam para ela (`Pagamento.comissao`), e o estorno de um deles, descontado depois, aponta para a comissão que o descontou (`Pagamento.comissao_estorno`); assim nenhum recebimento é comissionado duas vezes. Cancelar o lançamento a pagar cancela a comissão e solta os pagamentos |
| `ImportacaoExtrato` | clinica, conta, arquivo, código do banco, conta no banco, início, fim, saldo no banco e data, transações novas e já importadas, importado por/em | Desde a 0.20. O arquivo OFX não é guardado, só as transações |
| `TransacaoBancaria` | clinica, conta, importação, identificador no banco (FITID), data, valor (positivo entra, negativo sai), descrição, tipo no banco, situação (pendente, conciliada, ignorada), pagamento ou movimento do caixa (no máximo um), motivo, conciliado por/em | Única por conta e identificador: reimportar não duplica. Um pagamento só concilia com uma transação; estornado, a transação volta a pendente |

As contas a pagar (0.16.0) usam as mesmas entidades. Desde a 0.37.0, a conta a pagar pode ter um `Fornecedor` cadastrado (pessoa física ou jurídica, CPF/CNPJ único na clínica, telefone, WhatsApp, e-mail, ativo), cujo nome também é copiado no campo do pagador; um pagamento avulso continua aceitando o nome digitado. As metas do ano são linhas `Planejamento` (ano, grupo, valor; decisão 098). As categorias podem pertencer a um `GrupoContabil` (plano de contas: nome, tipo, grupo acima e código opcionais, ativo; decisão 097). O lançamento também pode ter um `CentroCusto` (centro de custo: nome, ativo; um por lançamento, opcional, decisão 095). Os convênios (app `convenios`, 0.37.0) são `Convenio` (nome, registro na ANS, telefone, ativo) e a `Carteirinha` do paciente (convênio, plano, número único no convênio, validade, titular, ativa). O saldo de cada conta é o saldo inicial mais o que entrou menos o que saiu (pagamentos não estornados). Valores em `Decimal` com 2 casas. A parcela é travada no banco ao receber, para duas pessoas não pagarem a mesma parcela além do saldo. Na exclusão definitiva de um paciente, os lançamentos dele ficam (histórico contábil) com o pagador "Paciente excluído (código N)", e a auditoria deles perde os dados pessoais.

### Orçamentos (versão 0.18.0)
| Entidade | Campos principais | Observação |
|---|---|---|
| `Procedimento` | clinica, nome, valor, categoria de receita, ativo | Tabela de preços da clínica |
| `Orcamento` | clinica, paciente, profissional, data, validade, situação (em aberto, aprovado, recusado), desconto (só administrador), observações, lançamento a receber, aprovado ou recusado em/por, criado por | Aprovado, vira um `Lancamento` a receber e não muda mais |
| `ItemOrcamento` | clinica, orçamento, procedimento (opcional), descrição, dentes (FDI, separados por vírgula), faces ou região, quantidade, valor unitário | Descrição e valor copiados da tabela no momento; mudar a tabela não altera orçamentos |

Na exclusão definitiva de um paciente, os orçamentos dele são apagados (os dentes são dado de saúde) e a auditoria deles perde os dados pessoais.

### Sistema
| Entidade | Uso |
|---|---|
| Releases | Lidas do arquivo `releases.yaml` (não ficam no banco). Veja [versionamento-e-releases.md](versioning.md) |
| `RegistroAuditoria` | Quem criou, alterou ou excluiu o quê e quando (LGPD) |
| `Backup` | Cada backup diário enviado ao Cloud Storage, registrado pelo servidor. Se o último tiver mais de 26 horas, os superusuários veem um aviso no topo das telas |

## Agenda
- `Agendamento` guarda início e fim como data e hora com fuso. Os agendamentos de uma mesma repetição semanal compartilham o campo `serie`.
- Regras: horários alinhados à duração configurada da clínica e dentro do expediente; sem sobreposição para o mesmo profissional (horários encostados são permitidos).
- A sobreposição é verificada no formulário (com mensagem de quem conflita) **e** por uma *exclusion constraint* do PostgreSQL (`btree_gist`), que vale mesmo com duas pessoas gravando ao mesmo tempo. Agendamentos **desmarcados** (0.24) ficam fora das duas verificações: continuam no histórico, mas liberam o horário.

## Auditoria (LGPD)
- `RegistroAuditoria` (`apps/auditoria`) guarda **quem**, **quando**, **de qual IP**, **qual ação** e, nas alterações, o **antes e depois** de cada campo.
- Registrado automaticamente (sinais do Django): criar, alterar e excluir Paciente, Agendamento, Rechamada, Profissional, TipoAtendimento, Clínica, Vínculo e Usuário. Também: abrir a ficha de um paciente, entrar, sair e tentativas de entrada recusadas.
- **Nunca** grava senhas nem o hash delas (a troca de senha aparece só como "alterada").
- Os registros guardam os códigos de clínica e usuário sem chave estrangeira rígida: o histórico sobrevive à exclusão de um usuário ou clínica. Não podem ser editados nem excluídos (admin somente leitura), com uma exceção: as tentativas de entrada recusadas, que guardam o usuário digitado, são apagadas depois de 30 dias pelo comando `aplicar_retencao`, que o servidor roda todo dia junto com o backup (decisão 045). Nos backups, elas duram mais 30 dias. Na exclusão definitiva de um paciente, os registros dele perdem os dados pessoais (ver abaixo).
- O nome do tipo de registro é gravado sempre em português, qualquer que seja o idioma do usuário: os filtros e a anonimização dependem dele.
- Tela **Cadastros > Auditoria**, só para o administrador da clínica, filtrada pela clínica atual. Alterações em contas de usuário (que não pertencem a uma clínica) ficam registradas na clínica em que foram feitas. Entradas no sistema (login) não pertencem a uma clínica e aparecem só para o superusuário, no admin.

## Idioma do usuário
`Usuario.idioma` guarda o idioma escolhido (`pt-br`, `en`, `es` ou vazio para seguir o navegador). Não entra na auditoria, como a última versão vista.

## Ficha do paciente
Mostra identificação, contato, observações, os próximos e os últimos 10 agendamentos (versão 0.12.0; para o profissional, só os da própria agenda, com link para a semana na agenda) e as rechamadas.

## Pacientes inativos, arquivados e excluídos (versão 0.9.0)
- **Inativo:** parou de vir, mas continua visível para toda a equipe (filtro "Inativos"). Não aparece nos aniversariantes.
- **Arquivado** (substitui o "excluir" do dia a dia, decisão 046): o paciente sai das listas, da busca, da agenda (sugestões), dos aniversariantes e das rechamadas da equipe. Nada é apagado: agendamentos, rechamadas e auditoria continuam, e os agendamentos antigos seguem mostrando o nome. Só o administrador da clínica arquiva, vê os arquivados (lista de pacientes, Situação: Arquivados) e restaura. O CPF/CNPJ de um arquivado continua reservado; a tela avisa para pedir a restauração.
- **Excluído definitivamente:** só a partir de um paciente arquivado, pelo administrador, quando o próprio paciente pede a exclusão dos dados (LGPD, art. 18). O cadastro e as rechamadas são apagados, os agendamentos ficam sem o paciente, e os registros de auditoria do paciente, dos seus agendamentos e rechamadas perdem os dados pessoais (`apps/auditoria/registro.py`, `anonimizar`): ficam quem fez, o quê, quando, o código e os nomes dos campos. A tela lembra que a clínica pode ser obrigada a guardar o prontuário (Lei 13.787/2018).

## Documentos e formatos
- CPF, CNPJ, telefones e CEP são guardados **sem pontuação** e formatados só na exibição (filtros em `apps/core/templatetags/formatos.py`).
- O CNPJ aceita o **formato alfanumérico** da Receita Federal (em vigor desde julho de 2026: letras nas 12 primeiras posições, dígitos verificadores numéricos). Validação em `apps/core/validadores.py`.
- O CPF/CNPJ é opcional (crianças, por exemplo), mas **único dentro da clínica** quando informado.

## Diferenças intencionais em relação ao sistema antigo
| Antes | Agora | Motivo |
|---|---|---|
| Dentista | Profissional | Sistema genérico |
| Cores fixas da agenda | Tipos de atendimento configuráveis por clínica | Cada especialidade tem os seus |
| Agendamento só com texto livre | Paciente **opcional** vinculado + descrição | Base para o app do paciente, sem perder o uso rápido |
| Tabelas de bairro e logradouro mantidas à mão | Endereço em campos de texto + UF e cidade da tabela do IBGE | Menos manutenção. A busca por CEP entra depois |
| Saldo, data de pagamento, banco, agência e conta no paciente | **Fora da fase 1** | Pertencem a um futuro módulo financeiro |
| MSN, homepage, fax | Removidos | Obsoletos |
| Datas `0000-00-00` | Campos opcionais (NULL) | Integridade |
| Sem chaves estrangeiras | Chaves estrangeiras e índices | Integridade e desempenho |

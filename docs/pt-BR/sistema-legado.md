# Sistema legado (Odonto System)

[🇺🇸 English](../en/legacy-system.md) | 🇧🇷 Português

Referência para a reescrita. O código antigo (PHP) e os backups ficam **fora do repositório**, na pasta local `~/medical-system-old_data/` (acesso só do dono). A análise completa está em `~/medical-system-old_data/legado-php/ANALISE_SISTEMA.md`.

> Os backups têm dados reais de pacientes (LGPD). **Nunca** copiar nada de lá para o repositório, para imagens Docker ou para os testes, que usam apenas **dados fictícios**. Por segurança, `old_data/` continua no `.gitignore` e no `.dockerignore`.

## Resumo
- PHP 5.3 sem framework, MySQL 5.5 (MyISAM, latin1), jQuery 1.x. Escrito em 2009–2010, usado até nov/2019.
- ~20 mil linhas, ~110 páginas, 17 tabelas.
- Não roda em PHP atual (`mysql_*` foi removido no PHP 7).

## Funções a reproduzir (paridade)
| Módulo | Comportamento a manter |
|---|---|
| Login | Usuário + senha. Usuário inativo não entra. Tela inicial com usuário e grupo |
| Permissões | Por grupo e item de menu: consultar, cadastrar, alterar, excluir. Botões aparecem conforme a permissão |
| Pessoas | PF/PJ, endereço encadeado (UF → cidade → bairro → logradouro), 4 telefones, observações, ativo. Lista paginada alfabética, busca por nome, ID e CPF/CNPJ. Visualizar, alterar, excluir com confirmação. Idade calculada |
| Agenda | Semana seg–dom, 07:30–20:00, slots de 30 min, por dentista (escolhido num select e lembrado na sessão). Navegação `<<`/`>>` e "ir para data". Bloco colorido por tipo. Legenda de cores. Clique em slot vazio abre o cadastro (dentista, tipo, início, fim, data, descrição). Repetição "acontece N vezes" (semanal). Horários só em :00/:30. Conflito de horário do mesmo dentista bloqueia a gravação. Editar e excluir no bloco. Ícones de rechamadas e aniversariantes no rodapé de cada dia |
| Rechamadas | Pessoa + data + descrição. Listar, cadastrar, alterar. Aparece na agenda |
| Aniversariantes | Lista por mês (nome + data) com link para a ficha |
| Dentistas | CRUD (nome) |
| Tabelas base | UF, cidade, bairro, logradouro, banco, tipo de endereço, estado civil |
| Sistema | CRUD de usuários e grupos, regeneração de permissões padrão |

## Revisão de paridade (26/10/2026)
Os 185 arquivos PHP foram comparados com o sistema novo.
- **Reproduzido:** tudo da tabela acima, inclusive a gestão de usuários, que chegou na versão 0.8.0 (tela Equipe, com papéis fixos no lugar de grupos configuráveis; decisão 040). Bairro, logradouro e tipo de endereço viraram campos de texto (ver [modelo-de-dados.md](modelo-de-dados.md)).
- **Não havia módulo financeiro:** nada de caixa, contas a receber ou orçamentos. Só os campos saldo, data de pagamento e banco/agência/conta em `pessoas`, mais observações livres. Confirmado em todos os dumps (2011–2019, sempre as mesmas 17 tabelas) e nos arquivos compactados (`www*.rar` têm os mesmos 185 arquivos PHP). Um financeiro, se vier, será feito do zero.
- **Não portado de propósito** (código morto no sistema antigo): pessoas relacionadas (a página de destino nunca existiu), `config_imp.php` (sem link em nenhuma tela) e o campo `rg_obs`.

## Importação dos dados (versão 0.8.0)
O comando `importar_legado` (`apps/legado`) lê o dump do MySQL diretamente (sem precisar de MySQL) e cria tudo numa clínica nova, de uma vez: se algo falhar, nada fica gravado. Ele se recusa a importar numa clínica que já tenha pacientes.

```bash
docker compose exec -T app python manage.py importar_legado - --clinica "Nome da clínica" \
  < ~/medical-system-old_data/backup_20191106/facchini07_20191106.sql
```

| Sistema antigo | Sistema novo |
|---|---|
| `dentistas` | Profissionais (sem o `_` que o sistema antigo usava no início do nome para ordenar) |
| `agenda_cor` | Tipos de atendimento da clínica, associados pelo nome (sem acentos) |
| `pessoas` | Pacientes. A cidade é associada à lista do IBGE pelo nome; bairro e logradouro viram texto; o zero à esquerda perdido do CPF é recuperado; a data de cadastro é mantida |
| `agendax` | Agendamentos, só com a descrição, como no sistema antigo (sem paciente vinculado). Os sem descrição (horários bloqueados, como "Ocupado") recebem o nome do tipo, porque a agenda exige paciente ou descrição |
| `agenda` (rechamadas) | Rechamadas. As de datas passadas entram como concluídas, porque o sistema antigo não marcava conclusão |
| Usuários e grupos | Não importados: a equipe é cadastrada em **Cadastros > Equipe** |

- O que não tem campo próprio vai para as **observações** do paciente, num bloco "[Sistema antigo]": código antigo, saldo, data do último pagamento, banco/agência/conta, fax, site, MSN, além de documentos, e-mails, CEPs e cidades que não puderam ser usados (CPF/CNPJ inválido ou repetido, por exemplo). Nada é descartado.
- Telefones sem DDD ficam como estavam: a clínica tinha pacientes com DDD 51 e 54, então não dá para deduzir.
- Agendamentos sobrepostos ou sem profissional não entram, e o término antes do início vira 30 minutos. Se houver atendimentos fora do horário da agenda, o horário da clínica é ampliado. O comando mostra um relatório com a contagem de cada caso, e a importação fica registrada na auditoria da clínica.

Resultado com o dump de 06/11/2019, no ambiente **local** (27/10/2026): 1.093 pacientes, 18.590 agendamentos (2010–2020), 41 rechamadas e 2 profissionais. Ficaram de fora 1 agendamento sem profissional e 1 rechamada de paciente apagado; 37 CPF/CNPJ inválidos ou repetidos foram para as observações; a agenda passou a ir até 22:00. **Produção:** importado em 27/10/2026 na "Clínica Sorriso", com o mesmo resultado, depois de apagar os dados fictícios (`remover_dados_teste`). Os dados ficam nos EUA, por decisão do titular (ver LGPD em [arquitetura.md](arquitetura.md)); o procedimento está em [deploy.md](deploy.md).

## Tipos de atendimento originais (seed de teste)
Liberado `#b9f1a7` · Cirurgia `#f7a5a5` · Dentística `#f6f7a5` · Periodontia `#7b88cb` · Consulta Inicial `#e7a5f7` · Prótese `#fed27d` · Endodontia `#e96cd9` · Ortodontia `#a7eef1` · Atendimento de 15 em 15 `#d5dae6` · Ocupado `#a7bef1`

## Problemas que a reescrita resolve
SQL injection generalizado (inclusive no login), scripts de gravação sem verificação de login, senhas MD5 sem salt, credenciais no código, XSS, ausência de CSRF, erros ocultos, código duplicado, ausência de testes, layout não responsivo.

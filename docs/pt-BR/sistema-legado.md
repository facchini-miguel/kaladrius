# Sistema legado (Odonto System)

[🇺🇸 English](../en/legacy-system.md) | 🇧🇷 Português

Referência para a reescrita. O código antigo (PHP) fica na pasta local `old_data/legado-php/www/`, que é ignorada pelo Git e pelo Docker. A análise completa está em `old_data/legado-php/ANALISE_SISTEMA.md`.

> Os backups com dados reais de pacientes ficam em `old_data/` (só na máquina local). **Nunca** tirar nada de lá do `.gitignore` nem copiar para o código versionado. Este projeto usa apenas **dados fictícios**.

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

## Tipos de atendimento originais (seed de teste)
Liberado `#b9f1a7` · Cirurgia `#f7a5a5` · Dentística `#f6f7a5` · Periodontia `#7b88cb` · Consulta Inicial `#e7a5f7` · Prótese `#fed27d` · Endodontia `#e96cd9` · Ortodontia `#a7eef1` · Atendimento de 15 em 15 `#d5dae6` · Ocupado `#a7bef1`

## Problemas que a reescrita resolve
SQL injection generalizado (inclusive no login), scripts de gravação sem verificação de login, senhas MD5 sem salt, credenciais no código, XSS, ausência de CSRF, erros ocultos, código duplicado, ausência de testes, layout não responsivo.

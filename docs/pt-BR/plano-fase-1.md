# Plano da fase 1: web da equipe + dados de teste

[🇺🇸 English](../en/phase-1-plan.md) | 🇧🇷 Português

> Status: **concluída** na versão 0.7.0 (26/10/2026).

## Objetivo
Ter, rodando em **Docker local**, a web da equipe com **as mesmas funções do sistema antigo**, já multi-clínica, segura, com dados fictícios para teste e a página de Novidades. Versão alvo: **0.7.0** (cada etapa com recursos novos sobe o número do meio). A 1.0.0 fica para o primeiro uso real.

## Fora do escopo da fase 1
API e app (fase 2), login de paciente (fase 3), planos e cobrança (fase 4), deploy na nuvem (feito logo após a fase 1, ver [deploy.md](deploy.md)), financeiro, prontuário.

## Estrutura do projeto

```
medical-system/
├── docker-compose.yml        ambiente local: db (postgres:16) + app
├── Dockerfile
├── .env.example
├── pyproject.toml            versão, configuração do ruff, do pytest e da cobertura
├── requirements*.txt         dependências (fixadas)
├── releases.yaml
├── config/                   settings (um arquivo, configurado por .env), urls, api, wsgi
├── apps/
│   ├── core/                 Clinica, Usuario, Vinculo, papéis e permissões, isolamento por clínica, comandos
│   ├── referencias/          UF, Cidade, Banco, EstadoCivil (globais) + carga inicial
│   ├── pacientes/            Paciente (PF/PJ), busca, ficha
│   ├── profissionais/        Profissional
│   ├── agenda/               TipoAtendimento, Agendamento, grade semanal, repetição, conflito, aniversariantes
│   ├── rechamadas/           Rechamada
│   ├── auditoria/            RegistroAuditoria, sinais, tela de auditoria
│   └── novidades/            leitura do releases.yaml, página Novidades, versão no rodapé
├── templates/                layout base (Bootstrap 5 + HTMX), menu conforme as permissões
├── static/                   CSS, JS da agenda e bibliotecas (Bootstrap, HTMX, FullCalendar)
├── deploy/                   compose de produção, Caddyfile, scripts e timers da VM
├── tests/
└── docs/
```

## Etapas

| # | Etapa | Entrega | Versão |
|---|---|---|---|
| 1 ✅ | **Esqueleto** | Projeto Django, Docker Compose (Postgres + app), settings via `.env`, Ruff, pytest, CI no GitHub, login, página inicial, usuário `admin`. Adiantado da etapa 7: página Novidades, versão no rodapé e API `/api/v1/releases` | 0.1.0 |
| 2 ✅ | **Multi-clínica e permissões** | Clinica, Vinculo, papéis (admin da clínica, recepção, profissional), isolamento por clínica que falha fechado, matriz de permissões, seletor de clínica, admin restrito ao superusuário, testes de isolamento. Adiantado da etapa 3: cadastro de **Profissionais** (primeiro dado da clínica, usado para testar o isolamento de ponta a ponta) e a primeira parte do comando `popular_dados_teste` | 0.2.0 |
| 3 ✅ | **Referências e cadastros simples** | UF e cidades (lista oficial do IBGE), bancos (Banco Central), estado civil, carregados por migração e com busca sem acentos. Tipos de atendimento por clínica, com os 10 tipos e cores originais criados automaticamente em toda clínica nova. Menu Cadastros. Endpoint UF → cidades para o formulário de pacientes | 0.3.0 |
| 4 ✅ | **Pacientes** | Lista paginada, busca (nome, código, CPF/CNPJ), formulário único PF/PJ com validação de CPF/CNPJ, UF → cidade encadeado (HTMX), ficha com idade, exclusão com confirmação. CNPJ alfanumérico (julho/2026) aceito. Pacientes fictícios no `popular_dados_teste` (Faker) | 0.4.0 |
| 5 ✅ | **Agenda** | Grade semanal por profissional (FullCalendar), horário e slot configuráveis por clínica, cores e legenda, criar/editar/excluir em modal, repetição semanal N vezes, bloqueio de conflito (validação no servidor + constraint no banco), paciente opcional (busca enquanto digita), aniversariantes do dia, exclusão de um ou da série. Restrição no banco (PostgreSQL) contra sobreposição. As **rechamadas do dia** entram com o módulo de rechamadas (etapa 6) | 0.5.0 |
| 6 ✅ | **Rechamadas e aniversariantes** | Rechamadas (cadastro, filtros, concluir, na ficha do paciente e no cabeçalho dos dias da agenda). Aniversariantes por mês com idade a completar e link para a ficha | 0.6.0 |
| 7 ✅ | **Novidades** (restante) | Aviso "versão nova: veja o que mudou" até o usuário abrir, filtro por módulo | 0.7.0 |
| 8 ✅ | **Dados de teste** | Comando `manage.py popular_dados_teste`: 2 clínicas, ~1.200 pacientes fictícios (CPF/CNPJ válidos e falsos), profissionais, ~5.000 agendamentos em torno da data atual, rechamadas, um usuário por papel | 0.7.0 |
| 9 ✅ | **Qualidade** | Cobertura dos testes nas regras críticas (isolamento, conflito, permissões), `check --deploy` sem alertas, auditoria de alterações (LGPD), limite de tentativas de login (django-axes), cobertura medida no CI (mínimo 90%; atual 96%) | 0.7.0 |

## Regras de negócio (testadas automaticamente)
- Um usuário só vê e altera dados das clínicas às quais está vinculado.
- Agendamentos do mesmo profissional não podem se sobrepor (inclusive nas repetições: se uma ocorrência conflita, nenhuma é gravada e a tela mostra qual data conflitou).
- Horários alinhados ao slot da clínica (padrão 30 min).
- O CPF/CNPJ é válido e único dentro da clínica.
- As permissões controlam tanto a tela (botões) quanto o servidor (a requisição é bloqueada).

## Ferramentas novas (todas com licenças permissivas)
Django, Django Ninja (instalado já na fase 1 para o endpoint de releases), psycopg, argon2-cffi, django-axes (limite de tentativas de login), Gunicorn, WhiteNoise (arquivos estáticos), PyYAML, Faker (dados de teste), pytest-django, pytest-cov, Ruff. No front: Bootstrap 5, HTMX e FullCalendar via arquivos estáticos (sem build de Node).

## Verificação
1. `docker compose up` → sistema em `http://localhost:8000`.
2. `docker compose exec app python manage.py popular_dados_teste` → dados fictícios carregados.
3. Login com `admin` e com um usuário de cada papel, conferindo que o menu e os botões mudam conforme a permissão.
4. Agenda: criar com repetição, provocar um conflito, editar, excluir, trocar de profissional e de semana.
5. Um usuário da clínica A não acessa um paciente da clínica B, nem digitando a URL.
6. `docker compose exec app pytest` e `ruff check` passando.
7. Página Novidades mostrando as versões do `releases.yaml`.

## Premissas adotadas (o titular pediu para seguir sem confirmação a cada passo)
1. Multi-clínica desde já (decisão 012).
2. Endereço em campos de texto + UF/cidade, sem as tabelas de bairro e logradouro do sistema antigo.
3. Campos financeiros do paciente (saldo, data de pagamento, dados bancários) fora da fase 1.
4. Paciente opcional no agendamento, mantendo a descrição livre.

Qualquer uma pode ser revista; registrar a mudança em `decisoes/`.

## Pendências após a fase 1
A revisão de paridade com o sistema antigo (ver [sistema-legado.md](sistema-legado.md)) mostrou que tudo foi reproduzido, exceto a gestão de usuários e grupos.

| Pendência | Situação |
|---|---|
| Tela de gestão da equipe pelo administrador da clínica (usuários, papéis, ativar/desativar) | **Decisão do titular:** papéis fixos (recepção, profissional, administrador) ou grupos configuráveis com matriz de permissões, como no sistema antigo. Até lá, o superusuário gerencia usuários e vínculos no admin do Django |
| Tela de configurações da clínica (horário e slot da agenda) | Hoje só pelo admin do Django |
| Revisão da matriz de permissões (`apps/core/permissoes.py`) | Com o titular |
| Importar dados reais do sistema antigo (pacientes, agenda) | **Decisão do titular.** Fora do plano (decisão 008); envolve LGPD, pois o servidor fica nos EUA |
| Teste da agenda e das rechamadas no navegador | Com o titular |
| Logotipo (SVG) | Com o titular |

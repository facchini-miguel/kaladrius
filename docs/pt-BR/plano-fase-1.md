# Plano da fase 1: web da equipe + dados de teste

[🇺🇸 English](../en/phase-1-plan.md) | 🇧🇷 Português

> Status: **em andamento**. Etapas 1, 2 e 3 concluídas (versões 0.1.0, 0.2.0 e 0.3.0).

## Objetivo
Ter, rodando em **Docker local**, a web da equipe com **as mesmas funções do sistema antigo**, já multi-clínica, segura, com dados fictícios para teste e a página de Novidades. Versão alvo: **0.7.0** (cada etapa com recursos novos sobe o número do meio). A 1.0.0 fica para o primeiro uso real.

## Fora do escopo da fase 1
API e app (fase 2), login de paciente (fase 3), planos e cobrança (fase 4), deploy na nuvem (logo após a fase 1), financeiro, prontuário.

## Estrutura do projeto

```
medical-system/
├── docker-compose.yml        db (postgres:16) + app
├── Dockerfile
├── .env.example
├── pyproject.toml            dependências, versão, configuração do ruff e do pytest
├── releases.yaml
├── config/                   settings (um arquivo, configurado por .env), urls, api, wsgi
├── apps/
│   ├── core/                 Clinica, Usuario, Vinculo, papéis, middleware da clínica atual, auditoria
│   ├── referencias/          UF, Cidade, Banco, EstadoCivil (globais) + carga inicial
│   ├── pacientes/            Paciente (PF/PJ), busca, ficha
│   ├── profissionais/        Profissional
│   ├── agenda/               TipoAtendimento, Agendamento, grade semanal, repetição, conflito
│   ├── rechamadas/           Rechamada
│   ├── aniversariantes/      consulta por mês
│   └── novidades/            leitura do releases.yaml, página Novidades, versão no rodapé
├── templates/                layout base (Bootstrap 5 + HTMX), menu conforme as permissões
├── tests/
└── docs/
```

## Etapas

| # | Etapa | Entrega | Versão |
|---|---|---|---|
| 1 ✅ | **Esqueleto** | Projeto Django, Docker Compose (Postgres + app), settings via `.env`, Ruff, pytest, CI no GitHub, login, página inicial, usuário `admin`. Adiantado da etapa 7: página Novidades, versão no rodapé e API `/api/v1/releases` | 0.1.0 |
| 2 ✅ | **Multi-clínica e permissões** | Clinica, Vinculo, papéis (admin da clínica, recepção, profissional), isolamento por clínica que falha fechado, matriz de permissões, seletor de clínica, admin restrito ao superusuário, testes de isolamento. Adiantado da etapa 3: cadastro de **Profissionais** (primeiro dado da clínica, usado para testar o isolamento de ponta a ponta) e a primeira parte do comando `popular_dados_teste` | 0.2.0 |
| 3 ✅ | **Referências e cadastros simples** | UF e cidades (lista oficial do IBGE), bancos (Banco Central), estado civil, carregados por migração e com busca sem acentos. Tipos de atendimento por clínica, com os 10 tipos e cores originais criados automaticamente em toda clínica nova. Menu Cadastros. Endpoint UF → cidades para o formulário de pacientes | 0.3.0 |
| 4 | **Pacientes** | Lista paginada, busca (nome, código, CPF/CNPJ), formulário único PF/PJ com validação de CPF/CNPJ, UF → cidade encadeado (HTMX), ficha com idade, exclusão com confirmação | 0.4.0 |
| 5 | **Agenda** | Grade semanal por profissional (FullCalendar), horário e slot configuráveis por clínica, cores e legenda, criar/editar/excluir em modal, repetição semanal N vezes, bloqueio de conflito (validação no servidor + constraint no banco), paciente opcional, rechamadas e aniversariantes do dia | 0.5.0 |
| 6 | **Rechamadas e aniversariantes** | CRUD de rechamadas. Aniversariantes por mês com link para a ficha | 0.6.0 |
| 7 | **Novidades** (restante) | Aviso "versão nova: veja o que mudou" até o usuário abrir, filtro por módulo | 0.7.0 |
| 8 | **Dados de teste** | Comando `manage.py popular_dados_teste`: 2 clínicas, ~1.200 pacientes fictícios (CPF/CNPJ válidos e falsos), profissionais, ~5.000 agendamentos em torno da data atual, rechamadas, um usuário por papel | 0.7.0 |
| 9 | **Qualidade** | Cobertura dos testes nas regras críticas (isolamento, conflito, permissões), `check --deploy` sem alertas, auditoria de alterações | 0.7.0 |

## Regras de negócio (testadas automaticamente)
- Um usuário só vê e altera dados das clínicas às quais está vinculado.
- Agendamentos do mesmo profissional não podem se sobrepor (inclusive nas repetições: se uma ocorrência conflita, nenhuma é gravada e a tela mostra qual data conflitou).
- Horários alinhados ao slot da clínica (padrão 30 min).
- O CPF/CNPJ é válido e único dentro da clínica.
- As permissões controlam tanto a tela (botões) quanto o servidor (a requisição é bloqueada).

## Ferramentas novas (todas com licenças permissivas)
Django, Django Ninja (instalado já na fase 1 para o endpoint de releases), psycopg, argon2-cffi, django-axes (limite de tentativas de login), django-htmx, PyYAML, Faker (dados de teste), pytest-django, Ruff. No front: Bootstrap 5, HTMX e FullCalendar via arquivos estáticos (sem build de Node).

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

# Registro de decisões

[🇺🇸 English](../../en/decisions/README.md) | 🇧🇷 Português

Cada linha é uma decisão tomada, com data e motivo. Se uma decisão mudar, a linha antiga fica marcada como **substituída** e uma nova é adicionada, para manter o histórico.

| # | Data | Decisão | Motivo | Status |
|---|---|---|---|---|
| 001 | 2026-10-26 | Reescrever o Odonto System (PHP 5) do zero | Não roda em PHP atual e tem falhas graves de segurança | Aceita |
| 002 | 2026-10-26 | Back-end e web em **Python + Django** | Login, permissões e admin nativos, segurança por padrão, menor esforço até a paridade | Aceita |
| 003 | 2026-10-26 | API com **Django Ninja** | Sintaxe moderna (tipo FastAPI) dentro do Django, reaproveitando models e permissões | Aceita |
| 004 | 2026-10-26 | App em **React Native + Expo** | Um código para Android e iOS | Aceita |
| 005 | 2026-10-26 | Banco **PostgreSQL 16** em Docker | — | Aceita |
| 006 | 2026-10-26 | Tudo em **Docker Compose numa VM do Compute Engine**; sem Cloud Run e sem Cloud SQL | Mesmo ambiente local e em produção, sem dependência de serviço gerenciado. Free tier (e2-micro) para testes | Aceita |
| 007 | 2026-10-26 | PHP e .NET descartados | Preferência do titular | Aceita |
| 008 | 2026-10-26 | **Sem migração dos dados antigos**; usar dados fictícios de teste | O sistema antigo não é mais usado | Aceita |
| 009 | 2026-10-26 | Sistema **genérico** ("Profissional" no lugar de "Dentista") | Atender qualquer tipo de clínica | Aceita |
| 010 | 2026-10-26 | Dois repositórios **privados**: `medical-system` e `medical-system-app` | Ciclos de vida e licenças independentes | Aceita |
| 011 | 2026-10-26 | Licença **proprietária** (todos os direitos reservados), em nome de Miguel Facchini (pessoa física) | Preserva todas as opções futuras (AGPL, MIT, comercial) | Aceita |
| 012 | 2026-10-26 | **Multi-clínica** desde a fase 1 | Possível venda como serviço (app grátis + web paga). Adaptar depois seria caro | Aceita (titular pediu para seguir com o padrão recomendado) |
| 013 | 2026-10-26 | Histórico de versões em `releases.yaml`, exibido no sistema e no app | Fonte única, versionada junto com o código | Aceita |
| 014 | 2026-10-26 | Versionamento semântico, começando em 0.1.0 | Padrão de mercado; a 1.0.0 é a primeira em uso real | Aceita |
| 015 | 2026-10-26 | Não usar dependências GPL/AGPL | Manter livre a escolha de licença | Aceita |
| 016 | 2026-10-26 | Django 6.1 (atual), migrar para a 6.2 LTS em abr/2027; Python 3.13 | Versão estável mais recente; LTS com suporte até 2030 | Aceita |
| 017 | 2026-10-26 | Front sem build de Node: Bootstrap 5.3 e HTMX 2 servidos como arquivos estáticos | Menos ferramentas para manter | Aceita |
| 018 | 2026-10-26 | Documentação bilíngue: `docs/pt-BR/` (principal) e `docs/en/` (tradução); `README.md` em inglês e `README.pt-BR.md` em português | Arquivos separados por idioma evitam texto misturado; inglês amplia o público se o projeto for aberto | Aceita |
| 019 | 2026-10-26 | Comentários e docstrings do código em inglês; textos para o usuário em português | Padrão internacional para o código, sem perder o idioma do público | Aceita |
| 020 | 2026-10-26 | Usar **somente recursos do free tier** do Google Cloud: e2-micro nos EUA também em produção, backup no Cloud Storage dos EUA, sem snapshots; alerta de orçamento de R$ 5 | Pedido do titular: custo zero | Aceita (substitui a parte de produção da 006: e2-small em São Paulo) |
| 021 | 2026-10-26 | Isolamento por clínica **que falha fechado**: gerenciador padrão filtra pela clínica atual e dá erro sem clínica; `sem_isolamento()` explícito para código da plataforma | Esquecer um filtro nunca vaza dados de outra clínica | Aceita |
| 022 | 2026-10-26 | Matriz de permissões por papel definida no código (`apps/core/permissoes.py`) | Simples e testável; revisão com o titular após a fase 1 | Aceita |
| 023 | 2026-10-26 | Admin do Django restrito aos superusuários da plataforma | O admin enxerga todas as clínicas | Aceita |
| 024 | 2026-10-26 | Cadastro de Profissionais antecipado para a etapa 2 | Primeiro dado da clínica; permite testar o isolamento de ponta a ponta | Aceita |
| 025 | 2026-10-26 | Tabelas de referência (UFs, municípios do IBGE, bancos do Banco Central) guardadas em JSON no repositório e carregadas por migração; busca sem acentos com a extensão `unaccent` do PostgreSQL | Dados oficiais, versionados e reproduzíveis em qualquer ambiente, sem depender de API externa | Aceita |
| 026 | 2026-10-26 | Tipos de atendimento por clínica, com os 10 tipos e cores do sistema antigo criados automaticamente em toda clínica nova | Paridade com o sistema antigo, mas editável por clínica | Aceita |
| 027 | 2026-10-26 | Cada etapa da fase 1 sobe a versão MENOR (0.3.0, 0.4.0…); a fase 1 termina na 0.7.0 | Etapas trazem recursos novos (regra do versionamento semântico) | Aceita |

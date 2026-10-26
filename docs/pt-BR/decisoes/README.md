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

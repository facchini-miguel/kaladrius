# Arquitetura

[🇺🇸 English](../en/architecture.md) | 🇧🇷 Português

## Visão geral

```
                          ┌── Web (Django templates + HTMX) ─── equipe da clínica
Django + PostgreSQL ──────┤
(um único back-end)       └── API /api/v1 (Django Ninja) ───┬── App: perfil profissional/equipe
                                                            └── App: perfil paciente
                                                                 + push (Firebase Cloud Messaging)
```

## Repositórios (privados)

| Repositório | Conteúdo | Fase |
|---|---|---|
| `medical-system` (este) | Django, web da equipe, API, Docker, documentação | 1 |
| `medical-system-app` | React Native + Expo (Android e iOS) | 2 |

Os dois se comunicam **somente pela API**.

## Stack do servidor

| Item | Escolha | Licença |
|---|---|---|
| Linguagem | Python 3.13 | PSF |
| Framework | Django (versão estável atual; migrar para a 6.2 LTS em abr/2027) | BSD |
| API | Django Ninja | MIT |
| Banco | PostgreSQL 16 | PostgreSQL (permissiva) |
| Interatividade web | HTMX | BSD |
| Calendário da agenda | FullCalendar (somente plugins gratuitos) | MIT |
| Estilo | Bootstrap 5 | MIT |
| Servidor de aplicação | Gunicorn | MIT |
| HTTPS / proxy | Caddy | Apache 2.0 |
| Testes | pytest + pytest-django | MIT |
| Lint e formatação | Ruff | MIT |

Regra: **não usar dependências GPL/AGPL**, para manter livre a escolha de licença do projeto.

## Execução (Docker Compose)

| Serviço | Imagem | Função |
|---|---|---|
| `db` | postgres:16-alpine | Banco, com volume persistente |
| `app` | imagem do projeto | Django + Gunicorn |
| `caddy` | caddy:2-alpine | HTTPS automático (só em produção) |
| `backup` | (fase de deploy) | pg_dump diário criptografado → Cloud Storage |

O mesmo `docker-compose.yml` serve para o ambiente local e para a VM, com diferenças apenas em `.env`.

## Infraestrutura

| Ambiente | Onde | Custo |
|---|---|---|
| Local | Docker no computador do desenvolvedor | — |
| Testes | VM e2-micro (free tier, EUA) | Grátis |
| Produção | VM e2-small, região São Paulo (`southamerica-east1`) | ~US$ 13–15/mês |

**CI/CD:** GitHub Actions roda lint e testes, gera a imagem no GitHub Container Registry e publica na VM por SSH (`docker compose pull && up -d`).

## Segurança (requisitos)
- Proteções nativas do Django ativas (CSRF, escape de XSS, ORM parametrizado, cabeçalhos de segurança). `manage.py check --deploy` sem alertas.
- Senhas com hash Argon2 e limite de tentativas de login.
- **Isolamento por clínica** em todas as consultas, com testes automatizados que tentam acessar dados de outra clínica.
- Segredos só em `.env` (fora do Git) e nos *Secrets* do GitHub. Push protection ativo.
- Postgres sem porta exposta. VM com firewall (80, 443, SSH só por chave).
- LGPD: registro de acessos e alterações (auditoria), dados no Brasil em produção, backups criptografados.

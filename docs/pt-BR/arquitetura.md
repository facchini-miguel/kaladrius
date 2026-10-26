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
| `backup` | (fase de deploy) | pg_dump diário criptografado → Cloud Storage (bucket nos EUA, free tier) |

O mesmo `docker-compose.yml` serve para o ambiente local e para a VM, com diferenças apenas em `.env`.

## Infraestrutura

Regra: **somente recursos do free tier do Google Cloud** (decisão 020).

| Ambiente | Onde | Custo |
|---|---|---|
| Local | Docker no computador do desenvolvedor | — |
| Nuvem (testes e produção) | VM **e2-micro** numa região gratuita dos EUA (`us-central1`, `us-west1` ou `us-east1`), disco padrão de até 30 GB | Grátis |
| Backup | Cloud Storage, bucket regional nos EUA, até 5 GB | Grátis |

**Projeto no Google Cloud:** `medical-system-facchini`, com a API do Compute Engine ativa e um **alerta de orçamento de R$ 5** (avisos em R$ 0,50, R$ 2,50 e R$ 5) para detectar qualquer cobrança.

**Limites do free tier a respeitar:** 1 VM e2-micro, 30 GB de disco padrão, 5 GB no Cloud Storage, 1 GB/mês de tráfego de saída. Snapshots de disco são pagos, por isso não são usados. O custo do IP externo da VM deve ser confirmado no primeiro relatório de faturamento.

**CI/CD:** GitHub Actions roda lint e testes, gera a imagem no GitHub Container Registry e publica na VM por SSH (`docker compose pull && up -d`).

## Segurança (requisitos)
- Proteções nativas do Django ativas (CSRF, escape de XSS, ORM parametrizado, cabeçalhos de segurança). `manage.py check --deploy` sem alertas.
- Senhas com hash Argon2 e limite de tentativas de login (django-axes: 5 erros por usuário + IP bloqueiam por 1 hora).
- Registro de auditoria de alterações, consultas a fichas e entradas no sistema (`apps/auditoria`).
- **No deploy:** atrás do Caddy, configurar o IP real do cliente (`X-Forwarded-For`) para o django-axes e a auditoria.
- **Isolamento por clínica** em todas as consultas, com testes automatizados que tentam acessar dados de outra clínica.
- Segredos só em `.env` (fora do Git) e nos *Secrets* do GitHub. Push protection ativo.
- Postgres sem porta exposta. VM com firewall (80, 443, SSH só por chave).
- LGPD: registro de acessos e alterações (auditoria), backups criptografados. Os dados ficam em servidores nos EUA (exigência do free tier). Antes de uso real com pacientes, revisar a transferência internacional de dados (LGPD, art. 33) ou migrar para uma região no Brasil.

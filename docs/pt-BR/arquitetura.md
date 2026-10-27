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
| Arquivos estáticos | WhiteNoise | MIT |
| Limite de tentativas de login | django-axes | MIT |
| HTTPS / proxy | Caddy | Apache 2.0 |
| Testes | pytest + pytest-django | MIT |
| Lint e formatação | Ruff | MIT |

Regra: **não usar dependências GPL/AGPL**, para manter livre a escolha de licença do projeto.

## Execução (Docker Compose)

| Serviço | Local (`docker-compose.yml`) | Produção (`deploy/docker-compose.prod.yml`) |
|---|---|---|
| `db` | postgres:16-alpine, volume persistente, sem porta exposta | Igual, com memória ajustada para a e2-micro |
| `app` | Imagem construída na máquina, código montado como volume, servidor de desenvolvimento do Django (recarrega ao salvar) | Imagem do Artifact Registry com Gunicorn, acessível só em `127.0.0.1:8000` |
| `caddy` | — | caddy:2-alpine na rede do host: HTTPS automático (Let's Encrypt) e proxy para o app |

Em produção, só o app recebe o `.env` inteiro; o banco recebe apenas as variáveis do Postgres e o Caddy, apenas o nome do site. Os nomes dos projetos são diferentes (`medical-system-dev` no local, `medical-system` na VM), para que os dois nunca compartilhem containers ou volumes na mesma máquina. Nos dois casos o app roda as migrações ao subir e lê a configuração do `.env`. O backup não é um serviço do Compose: um *timer* do systemd na VM roda `deploy/servidor/backup.sh` todo dia (`pg_dump` → Cloud Storage). Detalhes em [deploy.md](deploy.md).

## Infraestrutura

Regra: **somente recursos do free tier do Google Cloud** (decisão 020).

| Ambiente | Onde | Custo |
|---|---|---|
| Local | Docker no computador do desenvolvedor | — |
| Nuvem (testes e produção) | VM **e2-micro** em `us-east1-b`, disco standard de 30 GB, **somente IPv6 público** (o IPv4 é cobrado). Detalhes em [deploy.md](deploy.md) | Grátis |
| Backup | Cloud Storage, bucket regional nos EUA, até 5 GB | Grátis |

**Projeto no Google Cloud:** `medical-system-facchini`, com a API do Compute Engine ativa e um **alerta de orçamento de R$ 5** (avisos em R$ 0,50, R$ 2,50 e R$ 5) para detectar qualquer cobrança.

**Limites do free tier a respeitar:** 1 VM e2-micro, 30 GB de disco padrão, 5 GB no Cloud Storage, 1 GB/mês de tráfego de saída. Snapshots de disco são pagos, por isso não são usados. O IPv4 público de VMs é cobrado, por isso a VM só tem IPv6 público (decisão 035).

**CI/CD:** GitHub Actions roda lint e testes e publica a imagem no **Artifact Registry** do Google (autenticação sem chave). A VM verifica a cada 5 minutos e se atualiza sozinha (o GitHub não tem IPv6, então a VM não acessaria o GHCR, e o CI não alcançaria a VM por SSH).

## Segurança (requisitos)
- Proteções nativas do Django ativas (CSRF, escape de XSS, ORM parametrizado, cabeçalhos de segurança). `manage.py check --deploy` sem alertas.
- Senhas com hash Argon2 e limite de tentativas de login (django-axes: 5 erros por usuário + IP bloqueiam por 1 hora). Em IPv6 conta a rede /48, e não o endereço, porque trocar de endereço dentro da própria rede é trivial (decisão 041).
- Sem recuperação de senha por e-mail (o servidor não envia e-mails): cada pessoa troca a própria senha no menu com o seu nome, e o administrador da clínica define uma nova em Cadastros > Equipe (decisão 042).
- Registro de auditoria de alterações, consultas a fichas e entradas no sistema (`apps/auditoria`).
- Atrás do Caddy, o IP real do cliente vem do `X-Forwarded-For` (`DJANGO_PROXY_REVERSO=1`), usado pelo django-axes e pela auditoria.
- **Isolamento por clínica** em todas as consultas, com testes automatizados que tentam acessar dados de outra clínica.
- Segredos só em `.env` (fora do Git) e nos *Secrets* do GitHub. Push protection ativo.
- Postgres sem porta exposta. Firewall da VM: só TCP 80/443 e UDP 443 (HTTP/3) pela internet; SSH só pelo túnel IAP do Google.
- LGPD: registro de acessos e alterações (auditoria), backups em bucket privado, criptografados em repouso pelo Google (sem criptografia própria) e apagados após 30 dias. Se um backup falhar, o servidor tenta de novo; se o último tiver mais de 26 horas, os superusuários veem um aviso na web (decisão 043). Os dados ficam em servidores nos EUA (exigência do free tier). Antes de uso real com pacientes, revisar a transferência internacional de dados (LGPD, art. 33) ou migrar para uma região no Brasil.

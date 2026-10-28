---
sidebar_position: 2
title: Servidor próprio (Docker Compose)
---

# Servidor próprio (Docker Compose)

Este guia instala o Kaladrius em qualquer servidor Linux com Docker: uma VPS, uma máquina na clínica ou uma VM na nuvem. Ele roda três containers:

| Container | O que faz |
|---|---|
| `caddy` | Recebe os acessos nas portas 80 e 443, obtém o certificado HTTPS sozinho e repassa para o app |
| `app` | O Kaladrius (Django + Gunicorn), acessível só de dentro do servidor (`127.0.0.1:8000`) |
| `db` | PostgreSQL 16, com os dados num volume do Docker |

Confira antes os [requisitos](requirements.md): o domínio já precisa apontar para o servidor, e as portas 80 e 443 precisam estar abertas.

## 1. Instale o Docker e o Git

No Debian 13:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git
sudo systemctl enable --now docker
```

No Ubuntu, o pacote do plugin Compose se chama `docker-compose-v2` em vez de `docker-compose`. Confira com `docker compose version`.

Para outras distribuições, veja a [documentação do Docker](https://docs.docker.com/engine/install/).

## 2. Baixe o código

```bash
sudo git clone https://github.com/facchini-miguel/kaladrius.git /opt/kaladrius
cd /opt/kaladrius
```

## 3. Configure

```bash
sudo cp .env.example .env
sudo chmod 600 .env
sudo nano .env
```

Altere estes valores (a lista completa está em [Configuração](../configuration.md)):

```ini
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<um valor aleatório longo>
DJANGO_ALLOWED_HOSTS=clinica.exemplo.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://clinica.exemplo.com.br
DJANGO_SECURE=1
DJANGO_PROXY_REVERSO=1

POSTGRES_PASSWORD=<uma senha forte>

DJANGO_ADMIN_USERNAME=admin
DJANGO_ADMIN_PASSWORD=<uma senha forte>

# Usado pelo Caddy para o certificado HTTPS
SITE_HOSTNAME=clinica.exemplo.com.br
# A imagem montada no passo 4
IMAGEM_APP=kaladrius:latest
# A coleta da saúde do servidor só existe na instalação do Google Cloud
DJANGO_SAUDE_MONITORADA=0
```

Para gerar valores aleatórios: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.

:::tip
Deixe o `DJANGO_BACKUP_MONITORADO` ligado (o padrão): os superusuários veem um aviso no topo das telas quando nenhum backup foi registrado nas últimas 26 horas. [Backup e restauração](../operations/backup-restore.md) mostra como agendar backups que se registram sozinhos.
:::

## 4. Monte a imagem

```bash
sudo docker build -t kaladrius:latest .
```

:::tip Ou use a imagem publicada
Toda versão também é publicada em `ghcr.io/facchini-miguel/kaladrius` (tags `latest` e o número da versão, como `0.27.2`). Coloque-a em `IMAGEM_APP` no `.env` e pule este passo; para atualizar, `kaladrius pull app` e depois `kaladrius up -d`.
:::

## 5. Suba o sistema

Os comandos abaixo usam o arquivo de produção `deploy/docker-compose.prod.yml` com o seu `.env`. Para digitar menos, crie um atalho:

```bash
alias kaladrius='sudo docker compose -p kaladrius --env-file /opt/kaladrius/.env -f /opt/kaladrius/deploy/docker-compose.prod.yml'
```

(Coloque a linha no `~/.bashrc` para mantê-la.) Depois:

```bash
kaladrius up -d
kaladrius ps
```

O app aplica as migrações do banco toda vez que sobe. O Caddy pede o certificado ao Let's Encrypt no primeiro acesso; pode levar um minuto.

## 6. Crie o administrador

```bash
kaladrius exec app python manage.py criar_admin
```

Abra `https://clinica.exemplo.com.br`, entre e siga os [Primeiros passos](../first-steps.md) para criar a clínica e a equipe.

## Comandos úteis

```bash
kaladrius ps                                   # estado dos containers
kaladrius logs -f app                          # log do app (Ctrl+C para sair)
kaladrius logs -f caddy                        # problemas de HTTPS e de acesso
kaladrius exec app python manage.py <comando>  # comandos do Django
kaladrius restart app                          # reiniciar depois de mudar o .env
kaladrius down                                 # parar (os dados ficam)
```

Em seguida: [Atualização](../operations/upgrade.md) e [Backup e restauração](../operations/backup-restore.md).

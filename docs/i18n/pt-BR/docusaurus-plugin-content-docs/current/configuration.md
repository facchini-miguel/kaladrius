---
sidebar_position: 4
title: Configuração
---

# Configuração

Tudo o que muda de uma instalação para outra fica no arquivo **`.env`**, junto do código (servidor próprio) ou em `/opt/kaladrius/.env` (Google Cloud). Ele tem senhas: deixe-o legível só pelo root (`chmod 600`) e nunca o coloque no Git.

Depois de alterar, reinicie: `kaladrius up -d` (os containers com configuração alterada são recriados).

## Django

| Variável | Padrão | O que faz |
|---|---|---|
| `DJANGO_SECRET_KEY` | **obrigatória** | Assina sessões e tokens. Um valor aleatório longo; trocá-lo desconecta todo mundo |
| `DJANGO_DEBUG` | `0` | `1` mostra os detalhes dos erros. **Nunca `1` num servidor** |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Domínios a que o sistema responde, separados por vírgula |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vazio | Os mesmos domínios com `https://`, separados por vírgula |
| `DJANGO_SECURE` | `0` | `1` liga as proteções de HTTPS: redireciona para HTTPS, cookies seguros, HSTS de um ano. Use `1` num servidor |
| `DJANGO_PROXY_REVERSO` | `0` | `1` quando atrás do Caddy (ou outro proxy): pega o IP do visitante do `X-Forwarded-For`, para a auditoria e o bloqueio de login |
| `DJANGO_DEMONSTRACAO` | desligado | Só no servidor da demonstração pública: liga o reinício diário da demonstração (decisão 086). Nunca no servidor de uma clínica |
| `DJANGO_BACKUP_MONITORADO` | ligado quando `DJANGO_DEBUG=0` | Avisa os superusuários quando nenhum backup foi registrado nas últimas 26 horas |
| `DJANGO_SAUDE_MONITORADA` | ligado quando `DJANGO_DEBUG=0` | Avisa os superusuários quando a coleta da saúde do servidor para ou um recurso fica crítico. Use `0` fora da instalação do Google Cloud |
| `DJANGO_SAUDE_DIR` | `/saude` | Pasta, dentro do container, com as amostras de saúde |
| `DJANGO_DOCS_URL` | `https://kaladrius-docs.facchini.eti.br` | Este site de documentação. O menu **Ajuda** abre o site no idioma do usuário |

## Banco de dados

| Variável | Padrão | O que faz |
|---|---|---|
| `POSTGRES_DB` | `kaladrius` | Nome do banco |
| `POSTGRES_USER` | `kaladrius` | Usuário do banco |
| `POSTGRES_PASSWORD` | vazio | Senha do banco. Use uma forte |
| `POSTGRES_HOST` | `localhost` | `db` com o Docker Compose |
| `POSTGRES_PORT` | `5432` | |

O container do banco cria o banco e o usuário com esses valores na primeira vez que sobe. Mudá-los depois não altera um banco que já existe.

## Primeiro administrador

Usadas só pelo `python manage.py criar_admin`, que não faz nada se o usuário já existir.

| Variável | Padrão | O que faz |
|---|---|---|
| `DJANGO_ADMIN_USERNAME` | `admin` | Nome de usuário do superusuário |
| `DJANGO_ADMIN_PASSWORD` | **exigida pelo comando** | Senha do superusuário |
| `DJANGO_ADMIN_EMAIL` | vazio | E-mail do superusuário |

Depois do primeiro acesso, você pode tirar o `DJANGO_ADMIN_PASSWORD` do arquivo.

## Produção

| Variável | Padrão | O que faz |
|---|---|---|
| `SITE_HOSTNAME` | **obrigatória** | Domínio(s) que o Caddy atende e para os quais obtém o certificado HTTPS, separados por vírgula, ex.: `clinica.exemplo.com.br, www.clinica.exemplo.com.br` |
| `IMAGEM_APP` | o registro da instalação de referência | Imagem Docker do app, ex.: `kaladrius:latest` quando você mesmo monta |

## Só para desenvolvimento

| Variável | O que faz |
|---|---|
| `DJANGO_SEED_PASSWORD` | Senha dos usuários fictícios criados pelo `popular_dados_teste`. **Nunca** rode esse comando num servidor com dados reais: todos os usuários fictícios têm essa mesma senha |

## Configurações fixas

Ficam em `config/settings.py` e valem para todas as instalações:

- **Fuso horário** `America/Sao_Paulo` e **idioma padrão** português (cada usuário pode trocar para inglês ou espanhol).
- **Sessões** duram até 8 horas e terminam quando o navegador fecha.
- **Bloqueio de login:** 5 senhas erradas para o mesmo usuário a partir do mesmo endereço bloqueiam por 1 hora.
- **Envio de arquivos** até 6 MB (o maior é um extrato bancário OFX), limitado pelo Caddy.

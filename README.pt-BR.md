# Medical System

[🇺🇸 English](README.md) | 🇧🇷 Português

Sistema de gestão para clínicas: agenda por profissional, cadastro de pacientes, rechamadas (retornos), aniversariantes, usuários e permissões. Atende várias clínicas no mesmo servidor (multi-clínica).

É a reescrita do antigo *Odonto System* (PHP 5, 2009–2019), agora genérico para qualquer tipo de clínica.

[![CI](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml)

**Versão atual: 0.6.0** · [Novidades](releases.yaml) · [Todas as versões](https://github.com/facchini-miguel/medical-system/releases)

> Status: **fase 1 em andamento**.

## Como rodar (local)

Pré-requisito: Docker com Docker Compose.

```bash
cp .env.example .env          # preencha as senhas e a SECRET_KEY (valores aleatórios)
docker compose up --build -d  # sobe o banco e a aplicação
docker compose exec app python manage.py criar_admin   # cria o admin definido no .env
```

Acesse http://localhost:8000. A documentação da API fica em http://localhost:8000/api/v1/docs.

| Tarefa | Comando |
|---|---|
| Dados de teste (clínicas, usuários, profissionais, 600 pacientes fictícios por clínica 6 semanas de agenda e rechamadas) | `docker compose exec app python manage.py popular_dados_teste` |
| Testes | `docker compose exec app pytest` |
| Lint | `docker compose exec app ruff check .` |
| Formatar código | `docker compose exec app ruff format .` |
| Nova migração | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Parar | `docker compose down` (os dados do banco ficam no volume `pgdata`) |

## Stack

| Camada | Ferramenta |
|---|---|
| Servidor e web da equipe | Python + Django |
| API (para o app) | Django Ninja |
| Banco | PostgreSQL 16 |
| Execução | Docker + Docker Compose |
| Produção | VM do Google Compute Engine |
| App mobile | React Native + Expo, no repositório separado `medical-system-app` |

## Documentação

Toda a documentação fica em [`docs/`](docs/README.md), em português ([`docs/pt-BR`](docs/pt-BR/README.md)) e em inglês ([`docs/en`](docs/en/README.md)). O português é o idioma principal; o inglês é tradução.

## Versões

O histórico de versões fica em [`releases.yaml`](releases.yaml) e também pode ser consultado dentro do sistema e no app. Veja [docs/pt-BR/versionamento-e-releases.md](docs/pt-BR/versionamento-e-releases.md).

## Licença

Software proprietário. Todos os direitos reservados. Veja [LICENSE](LICENSE).

Desenvolvido por **Miguel Facchini**.

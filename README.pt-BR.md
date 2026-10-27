# Medical System

[🇺🇸 English](README.md) | 🇧🇷 Português | [🇪🇸 Español](README.es.md)

Sistema de gestão para clínicas: agenda por profissional, cadastro de pacientes, rechamadas (retornos), aniversariantes, usuários e permissões. Atende várias clínicas no mesmo servidor (multi-clínica).

É a reescrita do antigo *Odonto System* (PHP 5, 2009–2019), agora genérico para qualquer tipo de clínica.

[![CI](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/medical-system/actions/workflows/ci.yml)

**Versão atual: 0.21.1** · [Novidades](releases.yaml) · [Todas as versões](https://github.com/facchini-miguel/medical-system/releases)

> Status: **fase 1 concluída** (paridade com o sistema antigo), publicada em https://medical-system.duckdns.org (Google Cloud free tier, somente IPv6). Veja [docs/pt-BR/deploy.md](docs/pt-BR/deploy.md).

## Como rodar (local)

Pré-requisito: Docker com Docker Compose v2 (comando `docker compose`).

```bash
cp .env.example .env          # preencha as senhas e a SECRET_KEY (valores aleatórios)
docker compose up --build -d  # sobe o banco e a aplicação
docker compose exec app python manage.py criar_admin   # cria o admin definido no .env
```

Acesse http://localhost:8000. A documentação da API fica em http://localhost:8000/api/v1/docs.

| Tarefa | Comando |
|---|---|
| Dados de teste (clínicas, usuários, profissionais, 600 pacientes fictícios por clínica, 6 semanas de agenda e rechamadas) | `docker compose exec app python manage.py popular_dados_teste` |
| Compilar as traduções (depois de `git pull` ou de mudar textos; a imagem já faz isso no build) | `docker compose exec app python manage.py compilemessages` |
| Extrair textos novos para tradução (`locale/*/LC_MESSAGES/django.po`) | `docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests` |
| Apagar os dados de teste (nunca toca em clínicas e usuários reais) | `docker compose exec app python manage.py remover_dados_teste --confirmar` |
| Importar os dados do Odonto System antigo numa clínica nova (ver [docs/pt-BR/sistema-legado.md](docs/pt-BR/sistema-legado.md)) | `docker compose exec -T app python manage.py importar_legado - --clinica "Nome" < dump.sql` |
| Anonimizar os dados de uma clínica para usá-los como teste (irreversível) | `docker compose exec app python manage.py anonimizar_clinica --clinica "Nome" --confirmar` |
| Simular agenda e rechamadas atuais numa clínica de **teste** | `docker compose exec app python manage.py simular_movimento --clinica "Nome" --confirmar` |
| Título e texto da *Release* do GitHub (em inglês) | `docker compose exec app python manage.py notas_release X.Y.Z [--titulo]` |
| Testar a recuperação de um backup (baixa e restaura num PostgreSQL temporário) | `deploy/testar_backup.sh [arquivo.dump]` |
| Testes (com cobertura, mínimo de 90%) | `docker compose exec app pytest --cov` |
| Lint | `docker compose exec app ruff check .` |
| Formatar código | `docker compose exec app ruff format .` |
| Nova migração | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Parar | `docker compose down` (os dados do banco ficam no volume `medical-system-dev_pgdata`) |

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

Toda a documentação fica em [`docs/`](docs/README.md), em português ([`docs/pt-BR`](docs/pt-BR/README.md)), inglês ([`docs/en`](docs/en/README.md)) e espanhol ([`docs/es`](docs/es/README.md)). O português é o idioma principal; inglês e espanhol são traduções. O manual do usuário também está dentro do sistema, em **Ajuda > Manual do usuário**.

## Versões

O histórico de versões fica em [`releases.yaml`](releases.yaml) e também pode ser consultado dentro do sistema e no app. Veja [docs/pt-BR/versionamento-e-releases.md](docs/pt-BR/versionamento-e-releases.md).

## Licença

Software proprietário. Todos os direitos reservados. Veja [LICENSE](LICENSE).

Desenvolvido por **Miguel Facchini**.

# Medical System

Sistema de gestão para clínicas: agenda por profissional, cadastro de pacientes, rechamadas (retornos), aniversariantes, usuários e permissões. Atende várias clínicas no mesmo servidor (multi-clínica).

É a reescrita do antigo *Odonto System* (PHP 5, 2009–2019), agora genérico para qualquer tipo de clínica.

> Status: **fase 1 em andamento**. Versão atual: veja [`releases.yaml`](releases.yaml).

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

Toda a documentação fica em [`docs/`](docs/README.md).

## Versões

O histórico de versões fica em [`releases.yaml`](releases.yaml) e também pode ser consultado dentro do sistema e no app. Veja [docs/versionamento-e-releases.md](docs/versionamento-e-releases.md).

## Licença

Software proprietário. Todos os direitos reservados. Veja [LICENSE](LICENSE).

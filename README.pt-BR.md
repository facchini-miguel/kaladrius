<img src="static/img/logo.svg" alt="" width="72">

# Kaladrius

[🇺🇸 English](README.md) | 🇧🇷 Português | [🇪🇸 Español](README.es.md)

Sistema de gestão para clínicas: agenda por profissional, cadastro de pacientes, rechamadas (retornos), aniversariantes, usuários e permissões. Uma instalação atende uma clínica.

É a reescrita do antigo *Odonto System* (PHP 5, 2009–2019), agora genérico para qualquer tipo de clínica.

[![CI](https://github.com/facchini-miguel/kaladrius/actions/workflows/ci.yml/badge.svg)](https://github.com/facchini-miguel/kaladrius/actions/workflows/ci.yml)

**Versão atual: 0.63.0** · [Novidades](releases.yaml) · [Todas as versões](https://github.com/facchini-miguel/kaladrius/releases)

> Status: em desenvolvimento, em uso de demonstração. **Para conhecer, comece por https://www.facchini.eti.br/kaladrius/**: a página tem os acessos de demonstração de cada perfil (recepção, profissional, financeiro, administrador da clínica), as telas e todos os links. A demonstração roda no Google Cloud free tier, somente IPv6; veja [Produção de referência](https://kaladrius-docs.facchini.eti.br/pt-BR/project/production).

## Instalar num servidor

No Debian 13+ ou Ubuntu 24.04+, adicione o repositório de pacotes do Kaladrius e instale; algumas perguntas na tela (rede interna ou internet, o administrador) e o sistema está no ar, com backup diário, e as versões novas chegam com `sudo apt upgrade`:

```bash
sudo curl -fsSLo /etc/apt/sources.list.d/kaladrius.sources https://packages.facchini.eti.br/kaladrius/deb/kaladrius.sources
sudo apt update && sudo apt install kaladrius
```

Veja [Pacote Linux](https://kaladrius-docs.facchini.eti.br/pt-BR/installation/linux-package) para os detalhes (também os pacotes `.deb`, `.rpm` e do Arch Linux de cada [release](https://github.com/facchini-miguel/kaladrius/releases/latest)) e as outras formas de instalar (Docker Compose à mão, Google Cloud).

## Como rodar (local)

Pré-requisito: Docker com Docker Compose v2 (comando `docker compose`).

```bash
cp .env.example .env          # preencha as senhas e a SECRET_KEY (valores aleatórios)
docker compose up --build -d  # sobe o banco e a aplicação
docker compose exec app python manage.py create_admin   # cria o admin definido no .env
```

Acesse http://localhost:8000. A documentação da API fica em http://localhost:8000/api/v1/docs.

| Tarefa | Comando |
|---|---|
| Dados de teste (uma clínica, usuários, profissionais, 600 pacientes fictícios, 6 semanas de agenda e rechamadas) | `docker compose exec app python manage.py seed_sample_data` |
| Compilar as traduções (depois de `git pull` ou de mudar textos; a imagem já faz isso no build) | `docker compose exec app python manage.py compilemessages` |
| Extrair textos novos para tradução (`locale/*/LC_MESSAGES/django.po`) | `docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests` |
| Apagar os dados de teste (nunca toca em clínicas e usuários reais) | `docker compose exec app python manage.py remove_sample_data --confirm` |
| Importar os dados do Odonto System antigo numa clínica nova | `docker compose exec -T app python manage.py import_legacy - --clinic "Nome" < dump.sql` |
| Anonimizar os dados de uma clínica para usá-los como teste (irreversível) | `docker compose exec app python manage.py anonymize_clinic --clinic "Nome" --confirm` |
| Simular agenda e rechamadas atuais numa clínica de **teste** | `docker compose exec app python manage.py simulate_activity --clinic "Nome" --confirm` |
| Título e texto da *Release* do GitHub (em inglês) | `docker compose exec app python manage.py release_notes X.Y.Z [--title]` |
| Testar a recuperação de um backup (baixa e restaura num PostgreSQL temporário) | `deploy/test_backup.sh [arquivo.dump]` |
| Testes (com cobertura, mínimo de 90%) | `docker compose exec app pytest --cov` |
| Lint | `docker compose exec app ruff check .` |
| Formatar código | `docker compose exec app ruff format .` |
| Nova migração | `docker compose exec app python manage.py makemigrations` |
| Logs | `docker compose logs -f app` |
| Parar | `docker compose down` (os dados do banco ficam no volume `kaladrius-dev_pgdata`) |

## Stack

| Camada | Ferramenta |
|---|---|
| Servidor e web da equipe | Python + Django |
| API (para o app) | Django Ninja |
| Banco | PostgreSQL 16 |
| Execução | Docker + Docker Compose |
| Produção | VM do Google Compute Engine |
| App mobile | React Native + Expo, no repositório separado `kaladrius-app` |

## Documentação

Toda a documentação está no site **https://kaladrius-docs.facchini.eti.br/pt-BR/** (fonte em [`docs/`](docs/), Docusaurus): instalação, configuração, manual do usuário e as decisões do projeto, em português, inglês e espanhol.

## Versões

O histórico de versões fica em [`releases.yaml`](releases.yaml) e também pode ser consultado dentro do sistema e no app. A lista completa, com as notas de cada versão, está nas [Releases do GitHub](https://github.com/facchini-miguel/kaladrius/releases). Veja [Versões](https://kaladrius-docs.facchini.eti.br/pt-BR/project/versioning).

## Licença

Código aberto sob a [Licença Apache 2.0](LICENSE). O nome e o logo do Kaladrius não fazem parte da licença (veja [NOTICE](NOTICE)). Contribuições são bem-vindas: veja [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) e o [Código de Conduta](CODE_OF_CONDUCT.md).

Desenvolvido por **Miguel Facchini**.

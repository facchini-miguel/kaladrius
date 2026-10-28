---
sidebar_position: 2
title: Início rápido
---

# Início rápido

Rode o Kaladrius no seu computador, com dados fictícios, para conhecer. Você precisa do **Git** e do **Docker** (Docker Desktop no Windows e no macOS; Docker Engine com o plugin Compose no Linux).

:::warning
Esta instalação é **só para avaliação e desenvolvimento**: modo de depuração, sem HTTPS, usuários fictícios com a mesma senha. Para atender uma clínica, siga a [Instalação](installation/requirements.md).
:::

## 1. Baixe o código

```bash
git clone https://github.com/facchini-miguel/kaladrius.git kaladrius
cd kaladrius
```

## 2. Crie o arquivo de configuração

```bash
cp .env.example .env
```

O exemplo funciona como está no seu computador. Se quiser, troque as senhas (`POSTGRES_PASSWORD`, `DJANGO_ADMIN_PASSWORD`, `DJANGO_SEED_PASSWORD`) e a `DJANGO_SECRET_KEY`. Para gerar um valor aleatório:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 3. Suba o sistema

```bash
docker compose up --build
```

Da primeira vez leva alguns minutos (baixa o PostgreSQL e monta a imagem). Quando o log mostrar `Starting development server at http://0.0.0.0:8000/`, o sistema está no ar, mas ainda sem usuários.

## 4. Crie o administrador e os dados de exemplo

Em outro terminal, na mesma pasta:

```bash
docker compose exec app python manage.py criar_admin
docker compose exec app python manage.py popular_dados_teste
```

- `criar_admin` cria o **superusuário** com `DJANGO_ADMIN_USERNAME` e `DJANGO_ADMIN_PASSWORD`.
- `popular_dados_teste` cria uma clínica fictícia (marcada "(teste)") com pacientes, agenda, orçamentos e financeiro, e usuários de teste para cada perfil, todos com a senha `DJANGO_SEED_PASSWORD`.

## 5. Abra

Acesse **http://localhost:8000** e entre com o administrador. Use a bandeira na barra superior para mudar o idioma.

## Parar e limpar

```bash
docker compose down          # para; os dados ficam para a próxima vez
docker compose down -v       # para e apaga o banco de dados
```

Para apagar só os dados fictícios e manter o resto: `docker compose exec app python manage.py remover_dados_teste --confirmar`.

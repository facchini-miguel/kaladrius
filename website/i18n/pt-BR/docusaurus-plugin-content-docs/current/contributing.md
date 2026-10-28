---
sidebar_position: 10
title: Como contribuir
---

# Como contribuir

O Kaladrius é código aberto, sob a **Licença Apache 2.0**. Relatos de erros, traduções, documentação e código são bem-vindos.

## Relatar um erro ou pedir uma funcionalidade

Abra uma [issue](https://github.com/facchini-miguel/medical-system/issues) com o que você fez, o que esperava e o que aconteceu, a versão (no rodapé da página ou em `/api/v1/versao`) e, se possível, uma captura de tela. **Nunca anexe dados reais de pacientes.** Problemas de segurança vão em particular, veja [Segurança](security.md#como-relatar-uma-vulnerabilidade).

## Ambiente de desenvolvimento

Siga o [Início rápido](quick-start.md). A pasta do código fica montada no container e o servidor recarrega quando um arquivo é salvo. Depois:

```bash
docker compose exec app pytest --cov               # testes (a cobertura precisa ficar em 90% ou mais)
docker compose exec app ruff check .               # lint
docker compose exec app ruff format .              # formatação
docker compose exec app python manage.py makemigrations --check
```

## Convenções

- **Nomes do domínio em português** (`Paciente`, `Agendamento`), **comentários em inglês**.
- **Todo texto da tela** é escrito em português no código e traduzido em `locale/en` e `locale/es`:
  ```bash
  docker compose exec app python manage.py makemessages -l en -l es --no-location --ignore=staticfiles --ignore=tests
  ```
- **Documentação nos três idiomas:** uma mudança em `docs/pt-BR/` também muda `docs/en/` e `docs/es/` no mesmo commit; o mesmo vale para este site (`website/`).
- **Sem JavaScript embutido na página** (a Content Security Policy bloqueia): os scripts ficam em `static/js/`.
- **Decisões importantes** ganham um registro em `docs/<idioma>/decisoes/`.
- **Cada versão** ganha uma entrada no `releases.yaml`, mostrada em **Novidades**.

## Pull requests

1. Faça um fork, crie uma branch e faça a mudança com testes.
2. Confira se testes, lint e formatação passam.
3. Abra o pull request explicando o quê e por quê. Ao contribuir, você concorda que a sua contribuição fica sob a licença Apache 2.0.

## Este site de documentação

```bash
cd website
npm install
npm start                 # inglês, http://localhost:3000
npm run start:pt-BR       # português
npm run build             # todos os idiomas, em website/build
```

O manual do usuário não é editado aqui: ele vem de `docs/<idioma>/manual/`, os mesmos arquivos que o sistema mostra em **Ajuda**.

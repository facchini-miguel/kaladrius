---
sidebar_position: 10
title: Como contribuir
---

# Como contribuir

O Kaladrius é código aberto, sob a **Licença Apache 2.0**. Relatos de erros, traduções, documentação e código são bem-vindos.

## Relatar um erro ou pedir uma funcionalidade

Abra uma [issue](https://github.com/facchini-miguel/kaladrius/issues) com o que você fez, o que esperava e o que aconteceu, a versão (no rodapé da página ou em `/api/v1/version`) e, se possível, uma captura de tela. **Nunca anexe dados reais de pacientes.** Problemas de segurança vão em particular, veja [Segurança](security.md#como-relatar-uma-vulnerabilidade).

## Ambiente de desenvolvimento

Siga o [Início rápido](quick-start.md). A pasta do código fica montada no container e o servidor recarrega quando um arquivo é salvo. Depois:

```bash
docker compose exec app pytest --cov               # testes (a cobertura precisa ficar em 90% ou mais)
docker compose exec app ruff check .               # lint
docker compose exec app ruff format .              # formatação
docker compose exec app python manage.py makemigrations --check
```

## Convenções

- **Todo nome em inglês**: código, comentários, códigos gravados no banco, URLs, campos da API (decisões 144 a 200). Um app novo nasce em inglês: a pasta, o `label` (igual à pasta), modelos, campos e migrações (decisão 193).
- **Pastas e módulos dos apps com nome em inglês** (`apps/patients/`, `apps/core/countries.py`); o `label` de cada app é o nome da pasta (decisão 195). Os nomes dos arquivos de migração antigos ficam como estavam.
- **Comandos de gerenciamento com nome em inglês**, opções incluídas (`python manage.py seed_sample_data --patients 50`) (decisão 148).
- **Templates com nome em inglês**, numa pasta com o nome do seu app (`templates/patients/record.html`, `templates/finance/cash_flow.html`); os nomes do próprio Django ficam (`base.html`, `403.html`, `registration/login.html`) (decisão 146).
- **Arquivos de teste com nome em inglês**, pelo que testam (`tests/test_patients.py`, `tests/test_schedule.py`), mesmo quando o módulo testado tem nome em português (decisão 144). As funções de teste também, dizendo o que conferem (`test_duplicate_cpf_refused_in_same_clinic_but_allowed_in_another`); os textos que o teste procura na tela continuam em português (decisão 181). As fixtures, funções auxiliares e variáveis dos testes também são em inglês (`clinic_a`, `create_user`, `client_for`, `scenario`; decisão 188), e os dados fictícios ficam em português (`"Maria Paciente"`).
- **Todo texto da tela** é escrito em inglês no código, dentro de `_()` ou `{% translate %}`, e traduzido em `locale/pt_BR` e `locale/es` (decisão 200; o idioma padrão continua sendo o português do Brasil):
  ```bash
  docker compose exec app python manage.py makemessages -l pt_BR -l es --no-location --ignore=staticfiles --ignore=tests --ignore=docs
  ```
- **Documentação nos três idiomas:** tudo fica neste site (`docs/`): uma mudança numa página de `docs/docs/` também muda a mesma página em `docs/i18n/pt-BR/` e `docs/i18n/es/`, no mesmo commit.
- **Sem JavaScript embutido na página** (a Content Security Policy bloqueia): os scripts ficam em `static/js/`.
- **Decisões importantes** ganham um registro em `docs/<idioma>/decisoes/`.
- **Cada versão** ganha uma entrada no `releases.yaml`, mostrada em **Novidades**.

## Pull requests

1. Faça um fork, crie uma branch e faça a mudança com testes.
2. Confira se testes, lint e formatação passam.
3. Abra o pull request explicando o quê e por quê. Ao contribuir, você concorda que a sua contribuição fica sob a licença Apache 2.0.

A `main` só recebe mudanças por pull request, com merge depois que os checks `tests` e `docs` passam (decisão 141); não é preciso revisão aprovando. Num pull request de quem não é colaborador do repositório (em geral, de um fork), o CI só começa depois que um mantenedor clica em "Approve and run workflows", então os checks podem ficar esperando um pouco.

## Migrações do banco

Uma mudança num modelo precisa da migração dela (`python manage.py makemigrations`), no mesmo commit; sem ela, o CI falha. As migrações rodam sozinhas quando a versão nova sobe. Quando um pull request traz uma, o CI comenta nele o SQL que cada migração roda em produção, as operações que pedem atenção, as migrações já aplicadas que ele edita ou apaga, e um teste de que cada uma pode ser desfeita e aplicada de novo (`python manage.py migrations_report`).

A volta automática do servidor (decisão 135) põe o código anterior de volta, mas nunca desfaz uma migração. Então não apague nem renomeie de uma vez uma coluna que a versão atual usa: primeiro lance uma versão que pare de usá-la, e só depois a migração que a apaga. Uma coluna obrigatória nova tem o mesmo problema: os INSERTs da versão anterior a deixam de fora, então dê a ela `null=True` ou um `db_default` (um `default` do Python só preenche as linhas que já existem). E nunca edite uma migração que já está na `main`: produção não a roda de novo; escreva uma nova. O `--test-rollback` desfaz migrações, então só roda num banco descartável (o de testes, ou com `DISPOSABLE_DATABASE=1`, como no CI).

## Dependências

As bibliotecas que o sistema usa diretamente ficam em `requirements.in` (as ferramentas de teste e lint em `requirements-dev.in`). O `requirements.txt` e o `requirements-dev.txt` são **gerados** a partir delas, com todas as dependências, inclusive as indiretas, fixadas numa versão exata e com hash, para o CI e a imagem de produção instalarem exatamente a mesma coisa, e o pip recusa um pacote cujo hash não bate. Não edite os `.txt` à mão: mude o `.in` e gere-os de novo (precisa do Docker; usa o Python do `.python-version`):

```bash
deploy/lock.sh
```

O CI roda `deploy/lock.sh --check` e falha enquanto um lock não bater com o `.in` dele. O Dependabot atualiza os dois arquivos nos pull requests dele, inclusive as bibliotecas indiretas.

Os locks são resolvidos para Linux, onde o sistema roda. No Windows o `pip install` os recusa (um pacote que só o Windows precisa, como o `colorama`, não tem hash neles): desenvolva no Docker ([Início rápido](quick-start.md)) ou no WSL.

## Este site de documentação

Precisa do Node.js 26, a versão com que a imagem o gera (`docs/Dockerfile`).

```bash
cd docs
npm install
npm start                 # inglês, http://localhost:3000
npm run start:pt-BR       # português
npm run build             # todos os idiomas, em docs/build
```

O manual do usuário não é editado aqui: ele vem de `docs/<idioma>/manual/`, os mesmos arquivos que o sistema mostra em **Ajuda**.

---
sidebar_position: 8
title: Arquitetura
---

# Arquitetura

```
                          ┌── Web (templates Django + HTMX) ─── equipe da clínica
Django + PostgreSQL ──────┤
(um único back end)       └── API /api/v1 (Django Ninja) ───┬── App para profissionais e equipe (planejado)
                                                            └── App para pacientes (planejado)
```

## Tecnologias

| Camada | Escolha |
|---|---|
| Linguagem | Python 3.13 |
| Framework | Django, com Django Ninja para a API |
| Banco de dados | PostgreSQL 16 (regras como "dois agendamentos não ocupam o mesmo horário" ficam no próprio banco) |
| Páginas | Templates montados no servidor, HTMX para atualizar partes da tela, Bootstrap 5, FullCalendar na agenda |
| Servidor de aplicação | Gunicorn (2 processos × 4 threads, dimensionado para 1 GB de RAM) |
| HTTPS | Caddy com certificados automáticos do Let's Encrypt |
| Empacotamento | Imagem Docker; Docker Compose em desenvolvimento e produção |
| Idiomas | Traduções do Django (`locale/`): português, inglês e espanhol |
| Testes | pytest com cobertura (o build falha abaixo de 90%) |

## Código

```
config/           configurações, URLs, API
apps/
  core/           clínicas, módulos ligados/desligados, usuários, vínculos, permissões, tela de início
  agenda/         agenda e presença
  pacientes/      pacientes
  orcamentos/     orçamentos e tabela de procedimentos
  odontologia/    módulo de odontologia (odontograma), só com a especialidade Odontologia ligada
  convenios/      convênios e carteirinhas dos pacientes
  prontuario/     prontuário: anamnese de cada atendimento e adendos (só profissionais)
  rechamadas/     rechamadas e aniversariantes
  financeiro/     contas a receber e a pagar, caixa, bancos, comissões
  equipe/         gestão da equipe
  profissionais/  profissionais
  auditoria/      auditoria
  monitoramento/  saúde do servidor
  novidades/      versões e "Novidades"
  ajuda/          política de privacidade e links para este site
  legado/         importação do sistema PHP anterior
  referencias/    estados, cidades e outros dados de referência
templates/, static/, locale/
deploy/           compose de produção, Caddyfile, scripts do servidor
docs/             este site de documentação: instalação, manual, decisões
```

Os nomes no código seguem o domínio em **português** (`Paciente`, `Agendamento`), com comentários em inglês. Os dados de cada clínica levam a chave `clinica`, e as consultas filtram pela clínica em uso.

## Decisões

Toda decisão técnica e de produto importante fica registrada, com data e motivo, no [registro de decisões](project/decisions.md).

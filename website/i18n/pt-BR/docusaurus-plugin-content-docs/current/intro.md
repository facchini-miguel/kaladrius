---
slug: /
sidebar_position: 1
title: O que é o Kaladrius
---

# Kaladrius

O **Kaladrius** é um sistema de código aberto para administrar a clínica: agenda, cadastro de pacientes, orçamentos, rechamadas e financeiro, no navegador, para **dentistas e médicos**. Uma instalação atende uma clínica ou várias, cada uma com os seus dados, equipe e configurações.

> Nos bestiários medievais, o *kaladrius* (do grego *kharadriós*) era uma ave branca criada pelos reis: olhava para o doente, tomava a doença para si e voava com ela em direção ao sol. O nome é uma promessa de cuidado.

## O que ele faz

| Módulo | Destaques |
|---|---|
| **Início** | Resumo do dia: quem está agendado, quem veio, quem faltou, rechamadas, aniversariantes, caixa do dia e, para o administrador, o resultado do dia e do mês |
| **Agenda** | Visões de dia, semana e mês por profissional, controle de conflitos, presença (compareceu / faltou / desmarcou) |
| **Pacientes** | Pessoa física e jurídica, validação de CPF/CNPJ, contato e endereço, observações, agendamentos e rechamadas na ficha; pacientes ativos, inativos e arquivados |
| **Orçamentos** | Tabela de procedimentos, impressão, aprovação que gera as contas a receber |
| **Rechamadas e aniversariantes** | Quem ligar hoje, rechamadas atrasadas, aniversariantes com o celular à mão |
| **Financeiro** | Contas a receber parceladas, recibos, devedores, caixa do dia, contas a pagar, fluxo de caixa, relatórios, conciliação de extrato bancário (OFX), comissões |
| **Equipe e permissões** | Perfis de administrador, recepção e profissional; o profissional vê só a própria agenda e nenhum valor da clínica |
| **Auditoria** | Quem criou, alterou, excluiu ou abriu cada registro, quando e de onde |
| **Privacidade** | Feito para a LGPD: política de privacidade, registro de acessos, retenção de dados, exclusão definitiva de pacientes arquivados |

A tela funciona em **português, inglês e espanhol**; cada usuário escolhe o seu idioma.

## Como é feito

Uma única aplicação Python/Django com PostgreSQL, páginas montadas no servidor com HTMX (sem front-end pesado), uma API HTTP para os futuros aplicativos de celular e imagens Docker para a instalação. Roda bem numa máquina virtual de **1 GB de RAM**, como a do free tier do Google Cloud. Veja [Arquitetura](architecture.md).

## Por onde seguir

- **Experimentar no seu computador em 5 minutos:** [Início rápido](quick-start.md)
- **Instalar para uma clínica:** [Requisitos](installation/requirements.md), depois [servidor próprio](installation/docker-compose.md) ou [free tier do Google Cloud](installation/google-cloud.md)
- **Aprender a usar:** [Manual do usuário](manual/inicio.md)

## Licença

O Kaladrius é código aberto, sob a **Licença Apache 2.0**: você pode usar, alterar e redistribuir, inclusive comercialmente. Veja [Como contribuir](contributing.md).

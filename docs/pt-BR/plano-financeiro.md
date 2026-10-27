# Plano do módulo financeiro

[🇺🇸 English](../en/financial-plan.md) | 🇧🇷 Português | [🇪🇸 Español](../es/plan-financiero.md)

> Status: **concluído**: etapas 1 (a receber, 0.15.0), 2 (a pagar, fluxo de caixa e relatórios, 0.16.0) e 3 (caixa do dia, 0.17.0) (27/10/2026). Decisões 048 e 051. Juros e multa são lançados à mão, desconto só pelo administrador, e o endereço da clínica sai no recibo.

## Objetivo
Saber **quem deve o quê**, **como cada pessoa pagou** (dinheiro, Pix, cartão, parcelado) e **quanto entra e sai** da clínica, com lançamentos feitos à mão pela equipe.

## Fora do escopo (por decisão do titular)
- Emissão de nota fiscal (NFS-e) e do recibo do Receita Saúde.
- Integração com Pix, boleto, link de pagamento ou maquininha: o pagamento acontece fora do sistema e é **lançado** nele.
- Convênios odontológicos.

Tudo isso pode entrar depois; o modelo abaixo não impede.

## Conceitos

| Conceito | O que é | Exemplo |
|---|---|---|
| **Lançamento a receber** | Um valor que alguém deve à clínica, dividido em uma ou mais parcelas | Tratamento de canal de R$ 1.200 em 3 parcelas |
| **Lançamento a pagar** | Um valor que a clínica deve | Aluguel de R$ 3.000, todo dia 10 |
| **Parcela** | Valor e vencimento. Situação calculada: aberta, parcial, paga, vencida, cancelada | 2ª parcela, R$ 400, vence 10/12 |
| **Pagamento (baixa)** | Quanto foi pago de uma parcela, quando, como e para qual conta. Uma parcela pode ter vários (pagamento parcial) | R$ 400 no Pix em 08/12 |
| **Conta** | Onde o dinheiro fica | Caixa (dinheiro), Banco, Maquininha |
| **Categoria** | Para agrupar nos relatórios | Receitas: Tratamento, Consulta. Despesas: Aluguel, Material, Laboratório, Salários |

### Formas de pagamento
Dinheiro, Pix, cartão de débito, cartão de crédito (à vista ou parcelado na maquininha, com o número de parcelas), transferência, boleto (pago fora do sistema) e cheque. No cartão, guardam-se só a bandeira e o código da transação (NSU), **nunca** o número do cartão.

### Parcelado no cartão × parcelado com a clínica
- **No cartão:** o paciente paga tudo de uma vez (a operadora parcela para ele). A parcela do sistema fica **paga**; o paciente não deve nada.
- **Com a clínica (crediário, carnê, cheques):** o lançamento é criado com várias parcelas e vencimentos. O paciente **deve** cada parcela até pagar. É isso que aparece em "quem está devendo".

## Telas

| Tela | Conteúdo |
|---|---|
| **Financeiro > A receber** | Parcelas em aberto, filtros (vencidas, a vencer, período, paciente), botão **Receber** |
| **Novo lançamento a receber** | Paciente (opcional; ou nome do pagador), descrição, categoria, profissional (opcional), valor total, número de parcelas, primeiro vencimento e intervalo (mensal). As parcelas podem ser ajustadas antes de salvar. Opção "já recebido agora" para o caso comum de pagamento na hora |
| **Receber** | Valor (a parcela inteira ou parte), data, forma, conta, detalhes do cartão. Gera o recibo |
| **Recibo** | Página pronta para imprimir ou salvar em PDF pelo navegador |
| **Financeiro > Devedores** | Por paciente: total vencido e há quanto tempo (até 30, 31–60, 61–90 e mais de 90 dias), com link para a ficha |
| **Ficha do paciente** | Quadro "Financeiro": saldo devedor, parcelas abertas e últimos pagamentos |
| **Financeiro > A pagar** | Igual ao "A receber", com fornecedor no lugar de paciente e repetição mensal (cria as próximas parcelas) |
| **Financeiro > Fluxo de caixa** | Por dia ou mês: entradas e saídas **realizadas** (pagamentos) e **previstas** (parcelas em aberto), e saldo por conta |
| **Financeiro > Caixa do dia** | Entradas e saídas do dia por conta, retiradas (sangria) e reforço, fechamento com o valor conferido e a diferença |
| **Financeiro > Relatórios** | Recebido por forma de pagamento, por categoria e por profissional; despesas por categoria |
| **Cadastros > Financeiro** | Contas e categorias (cada clínica começa com uma lista padrão) |

## Regras
- Nada é apagado de verdade: lançamento vira **cancelado** e pagamento vira **estornado**, com motivo. Tudo fica na auditoria.
- A soma das parcelas é igual ao valor total; um pagamento não passa do que falta na parcela.
- Valores em reais com centavos (`Decimal`, nunca número com vírgula flutuante).
- Isolamento por clínica, como o resto do sistema.

## Permissões
Dois módulos novos na matriz:

| Módulo | Admin | Recepção | Profissional |
|---|---|---|---|
| **Recebimentos** (a receber, receber, recibo, devedores, caixa do dia) | tudo | ver, criar, alterar | — |
| **Financeiro** (a pagar, fluxo de caixa, relatórios, contas e categorias) | tudo | — | — |

Cancelar lançamentos e estornar pagamentos é só do administrador. Assim a recepção recebe e consulta quem deve, mas não vê salários e despesas da clínica.

## Etapas

| # | Etapa | Entrega | Versão |
|---|---|---|---|
| 1 ✅ | **A receber** | Modelos, contas e categorias padrão, lançamento a receber com parcelas, receber (todas as formas, parcial), recibo, devedores, quadro na ficha do paciente, permissões | 0.15.0 |
| 2 ✅ | **A pagar e fluxo de caixa** | Lançamento a pagar com repetição mensal, fluxo de caixa realizado e previsto, saldo por conta, relatórios | 0.16.0 |
| 3 ✅ | **Caixa do dia** | Abertura, sangria, reforço e fechamento com conferência | 0.17.0 |

### Depois (sem data)
Tabela de procedimentos e **orçamento** que vira lançamento a receber; **comissão dos dentistas**; resultado do período (DRE); taxas e datas de crédito da maquininha; importação do extrato bancário (OFX). E, se decidido: nota fiscal, Pix/boleto integrados, convênios.

## Premissas adotadas (podem ser revistas)
1. O financeiro vem **antes** da fase 2 (API e app).
2. Orçamento e comissão ficam para depois das 3 etapas.
3. Um lançamento a receber pode não ter paciente cadastrado (nome do pagador em texto).
4. Um lançamento a receber pode indicar o profissional, para a futura comissão.
5. Todo o módulo já nasce nos três idiomas da interface (as versões 0.13 e 0.14 trouxeram os idiomas e a Ajuda antes dele).

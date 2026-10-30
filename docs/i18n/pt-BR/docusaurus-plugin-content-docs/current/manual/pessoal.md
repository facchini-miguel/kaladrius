---
sidebar_position: 6.5
---

# Pessoal

O módulo **Pessoal** guarda os funcionários da clínica, os salários e as horas extras e faltas de cada mês, e transforma a folha do mês em contas a pagar no [financeiro](financeiro.md). Só o administrador e o perfil Financeiro veem. Ele pode ser desligado nas [configurações da clínica](clinica.md) e precisa do Financeiro ligado.

Encargos (INSS, FGTS), férias e 13º **não** são calculados: ficam com o contador ou com o sistema de folha.

## Funcionários
Em **Financeiro > Funcionários**, clique em **Novo funcionário**: nome, CPF, cargo, admissão, telefone e o **salário** (a partir da admissão, se você não escolher outra data). Num aumento, edite o funcionário e preencha **Novo salário** e a data a partir da qual vale: o salário anterior fica no **histórico de salários**, e cada mês usa o salário em vigor no fim dele. Quem saiu ganha uma **data de desligamento** e deixa de aparecer nos meses seguintes.

## A folha do mês
Em **Financeiro > Folha do mês**, escolha o mês. Aparece uma linha por funcionário que trabalhou nele, com o salário. Preencha:
- **Horas extras**: a quantidade e o valor da hora. O valor vem sugerido como salário ÷ 220 horas × 1,5 (o adicional mínimo para quem trabalha 44 horas por semana) e pode ser mudado.
- **Faltas**: os dias de falta; cada um desconta salário ÷ 30.

O **total** é salário + horas extras − faltas. **Salvar** guarda o que foi digitado. **Salvar e lançar no financeiro** transforma cada linha numa **conta a pagar** em nome do funcionário, na categoria escolhida (por padrão, "Salários e encargos") e com o vencimento escolhido. A linha lançada não muda mais nesta tela; para refazer, cancele a conta no financeiro e a linha volta a ficar aberta.

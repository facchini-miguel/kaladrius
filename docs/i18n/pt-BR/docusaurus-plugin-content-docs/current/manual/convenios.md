---
sidebar_position: 3.7
---

# Convênios

O módulo **Convênios** guarda os convênios que a clínica aceita e a carteirinha de cada paciente. Ele pode ser desligado nas [configurações da clínica](clinica.md) por quem só atende particular.

## Cadastrar um convênio
Em **Cadastros > Convênios**, clique em **Novo convênio** e preencha o nome e, se houver, o **registro da operadora** no país da clínica (no Brasil, a ANS, com 6 dígitos; nos Estados Unidos, o Payer ID; na Argentina, o RNOS; na África do Sul, o número no CMS), o telefone e observações. Nos países sem registro de operadoras o campo não aparece. O mesmo nome não pode ser cadastrado duas vezes. Para deixar de aceitar um convênio sem perder o histórico, edite e desmarque **ativo**: ele sai da lista das carteirinhas novas, e as existentes continuam.

## A carteirinha do paciente
Na ficha do paciente, o cartão **Convênios** lista as carteirinhas dele. Clique em **Nova carteirinha** e escolha o convênio, o **plano** (ex.: "Básico"), o **número da carteirinha**, a **validade** e, para um dependente, o **titular** do plano. O mesmo número de carteirinha não pode ser de dois pacientes no mesmo convênio.

O número da carteirinha leva o nome local (Member ID nos Estados Unidos, membership number no Reino Unido, na Austrália e na África do Sul, número de afiliado na Argentina…). As carteirinhas norte-americanas têm também o **número do grupo**, e as familiares da África do Sul e da Austrália o **código do beneficiário** (dependant code, número do paciente no cartão).

Uma carteirinha com a validade passada aparece como **Vencida**. Paciente sem carteirinha aparece como **Particular**. Uma carteirinha que não é mais usada pode ser marcada como inativa, sem ser apagada.

## Quem faz o quê
A recepção e o administrador cadastram convênios e carteirinhas; os profissionais e o perfil Financeiro consultam. Quando os dados de um paciente são excluídos a pedido dele (LGPD), as carteirinhas dele também são apagadas.

Guias, autorizações e faturamento para os convênios ainda não fazem parte do sistema.

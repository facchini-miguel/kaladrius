# Financeiro

O menu **Financeiro** mostra quem deve à clínica e como cada pessoa pagou. Os pagamentos acontecem fora do sistema (dinheiro, Pix, maquininha) e são **lançados** aqui. A recepção e o administrador usam; o profissional não vê o financeiro.

## Lançar um valor a receber
1. Em **Financeiro > Novo lançamento** (ou no quadro **Financeiro** da ficha do paciente), escolha o **paciente**. Se quem paga não for um paciente cadastrado, escreva o nome em **pagador**.
2. Informe a **descrição** (por exemplo, "Tratamento de canal"), a **categoria**, o **profissional** (opcional) e o **valor total**.
3. Em **Número de parcelas**, informe quantas vezes o paciente vai pagar **à clínica**, uma por mês, a partir do **vencimento da 1ª parcela**. As parcelas têm o mesmo valor; os centavos que sobram vão para a primeira.
4. Se o paciente pagou na hora, marque **A 1ª parcela já foi paga agora**, escolha a forma e a conta, e salve: o recibo abre em seguida.

**Parcelado no cartão não é parcelado com a clínica.** Se o paciente passou o cartão em 6 vezes, a clínica recebe da operadora: lance **1 parcela** e, ao receber, informe as 6 vezes no campo **parcelas no cartão**. O paciente não fica devendo nada.

## Receber
Em **Financeiro > A receber**, a lista mostra as parcelas em aberto (as vencidas em vermelho). Clique em **Receber** e informe:
- **valor recebido** (pode ser só uma parte: o resto continua em aberto);
- **juros e multa**, se cobrados, já incluídos no valor recebido (o cálculo é manual);
- **forma de pagamento** e **conta** (Caixa, Banco…);
- para cartão: bandeira, número de parcelas no cartão e código da transação. **Nunca** anote o número do cartão.

Só o administrador da clínica pode dar **desconto**.

## Recibo
Depois de receber, o recibo abre pronto para **imprimir ou salvar em PDF**. Ele mostra os dados da clínica (nome, CPF/CNPJ, endereço e telefone, de **Cadastros > Configurações da clínica**), quem pagou, o valor, a parcela e a forma de pagamento. Para reimprimir, abra o lançamento e clique em **recibo** ao lado do pagamento.

## Devedores
Em **Financeiro > Devedores**, cada paciente com parcelas vencidas, o total vencido separado por tempo de atraso (até 30, 31 a 60, 61 a 90 e mais de 90 dias), o que ainda vai vencer e o vencimento mais antigo. Clique no nome para abrir a ficha.

## Corrigir um erro
Nada é apagado. O **administrador** pode:
- **estornar** um pagamento lançado errado (abra o lançamento e clique em **estornar**, informando o motivo): a parcela volta a ficar em aberto e o recibo passa a mostrar "ESTORNADO";
- **cancelar** um lançamento (depois de estornar os pagamentos dele), informando o motivo.

Tudo fica registrado na auditoria.

## Caixa do dia
Em **Financeiro > Caixa do dia**, a recepção controla o dinheiro da gaveta:
1. **Abrir caixa:** conte o dinheiro e informe o valor. O sistema mostra quanto a conta deveria ter, só como referência.
2. Durante o dia, os pagamentos registrados na conta **Caixa** entram automaticamente.
3. **Retirada (sangria):** dinheiro que sai da gaveta, com o motivo. Se for depositado no banco, escolha a conta **Banco** em **Outra conta**; vazio, o dinheiro sai do sistema (por exemplo, uma retirada do dono).
4. **Reforço:** dinheiro que entra na gaveta, como troco.
5. **Fechar caixa:** conte de novo e informe o valor. O sistema mostra quanto deveria haver e registra a **diferença**; explique-a na observação, se houver.

Só pode haver um caixa aberto por conta. Os caixas fechados ficam em **Caixas anteriores**, com o esperado, o contado e a diferença.

## Contas a pagar (administrador)
Em **Financeiro > Nova despesa**, informe o **fornecedor**, a categoria, a descrição e o valor. Em **O valor é**, escolha:
- **o total, dividido nas parcelas**: uma compra de R$ 900 em 3 vezes vira 3 parcelas de R$ 300;
- **de cada mês**: uma conta fixa, como o aluguel de R$ 3.000 por 12 meses, vira 12 parcelas de R$ 3.000.

Em **Financeiro > A pagar**, clique em **Pagar** quando pagar uma parcela. Estornar e cancelar funcionam como nas contas a receber.

## Fluxo de caixa (administrador)
Em **Financeiro > Fluxo de caixa**, escolha o período e se quer ver por **dia** ou por **mês**:
- **Entradas** e **Saídas**: o que foi recebido e pago de fato, pela data do pagamento;
- **Entradas previstas** e **Saídas previstas**: o que falta das parcelas em aberto, pelo vencimento (as vencidas aparecem como "em atraso");
- **Saldo**: começa no saldo das contas no início do período e soma tudo, dia a dia (ou mês a mês).

Embaixo aparece o **saldo atual de cada conta**. Para ele bater com o banco e a gaveta, informe o **saldo inicial** de cada conta em **Cadastros > Contas** (quanto havia antes do primeiro lançamento no sistema).

## Relatórios (administrador)
Em **Financeiro > Relatórios**, para o período escolhido: total recebido, total pago e o resultado; recebido por forma de pagamento, por categoria e por profissional; e despesas pagas por categoria. Os pagamentos estornados e os lançamentos cancelados ficam de fora.

## Extrato bancário (administrador)
Em **Financeiro > Extrato bancário**, importe o extrato da conta, baixado do site ou aplicativo do banco no formato **OFX** (às vezes chamado "Money"). Escolha a conta do sistema (por exemplo, Banco) e o arquivo. Transações já importadas são puladas, então pode importar períodos que se sobrepõem. Se alguma linha do arquivo vier sem data ou valor que dê para ler, o sistema avisa quantas ficaram de fora: confira essas no extrato do banco.

Cada transação do banco é comparada com o que o sistema já tem nessa conta: um recebimento ou pagamento **com o mesmo valor, até 10 dias antes ou depois**, ou um depósito ou retirada do **caixa do dia** para essa conta.
- **Conciliar … com correspondência única** concilia de uma vez todas as transações que têm um só lançamento possível.
- Quando há mais de um possível, escolha na lista e clique em **Conciliar**.
- Sem nada no sistema (tarifa, rendimento, Pix que ninguém lançou), clique em **Criar lançamento**: o sistema cria a receita ou a despesa já paga nessa data e conta, e concilia.
- O que não deve virar lançamento (repasse da maquininha, transferência entre contas da clínica) pode ser **ignorado** com um motivo.
- **desfazer** volta a transação para pendente. Se um pagamento conciliado for estornado, a transação volta a ficar pendente.

No alto da tela, o **saldo no banco** informado no arquivo é comparado com o **saldo no sistema** na mesma data; com tudo lançado, a diferença fica em zero.

## Comissões (administrador)
Em **Financeiro > Comissões**, cada profissional tem um **percentual** sobre o valor recebido dos lançamentos a receber em que ele aparece (o orçamento aprovado já leva o profissional; num lançamento novo, escolha o profissional). Lançamentos sem profissional não geram comissão. A base é o valor que entrou, já com descontos e com juros, se houve.

1. Clique em **Percentual** para definir o de cada profissional.
2. Escolha a data em **Recebimentos até** (por exemplo, o último dia do mês) e clique em **Ver**: a tabela mostra o recebido ainda não comissionado e a comissão a pagar.
3. Clique em **Pagar**, confira os recebimentos e o vencimento e clique em **Lançar em A pagar**. A comissão vira uma despesa em **A pagar**, em nome do profissional, onde você registra o pagamento.

Cada recebimento entra numa comissão uma vez só. Se um recebimento já comissionado for **estornado**, a comissão dele é descontada no próximo pagamento ao profissional (pelo percentual da época). Se a despesa da comissão for **cancelada**, a comissão é desfeita e os recebimentos voltam a ficar pendentes. Se uma comissão posterior já descontou o estorno de um recebimento dela, cancele primeiro a posterior. O **Extrato** de cada comissão lista os recebimentos e os descontos e pode ser impresso para o profissional.

## Categorias e contas
Em **Cadastros > Categorias** e **Cadastros > Contas**, o administrador cria novas categorias (receitas e despesas) e contas (caixa, banco, maquininha). Para deixar de usar uma sem perder o histórico, desmarque **ativa**.

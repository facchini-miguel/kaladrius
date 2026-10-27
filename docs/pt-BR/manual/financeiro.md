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

## Categorias e contas
Em **Cadastros > Categorias** e **Cadastros > Contas**, o administrador cria novas categorias (receitas e despesas) e contas (caixa, banco, maquininha). Para deixar de usar uma sem perder o histórico, desmarque **ativa**.

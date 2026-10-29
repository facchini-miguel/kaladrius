---
sidebar_position: 3.5
---

# Prontuário

O prontuário guarda a **anamnese de cada atendimento**. Só os **profissionais** veem e escrevem nele: a recepção nunca, e o administrador da clínica só quando também está cadastrado como profissional (**Cadastros > Profissionais**, ligado ao usuário dele). O **administrador do sistema** vê e faz tudo: ao registrar um atendimento, escolhe em nome de qual profissional, e a auditoria guarda quem de fato fez.

## Registrar um atendimento
- Pela **agenda**: abra o agendamento do paciente e clique em **Registrar atendimento** (ou **Abrir atendimento**, quando ele já existe). O atendimento fica ligado ao agendamento e usa a data dele.
- Pela **ficha do paciente**: no quadro **Prontuário**, clique em **Novo atendimento**, para um atendimento fora da agenda.

A anamnese tem cinco campos, todos opcionais: **queixa principal**, **história da doença atual**, **antecedentes** (pessoais e familiares, medicamentos em uso, alergias), **exame físico** e **conduta e plano**.

## Rascunho, finalizar e adendos
- **Salvar rascunho** deixa o atendimento aberto: só quem escreveu pode alterar.
- **Salvar e finalizar** fecha de vez: a partir daí, ninguém altera. Correções e anotações posteriores são **adendos**, cada um com data e profissional; qualquer profissional da clínica pode incluir.
- O quadro **Prontuário** da ficha lista os atendimentos, do mais recente para o mais antigo, marcados como rascunho ou finalizado.

## Impressão, atestados e receitas
- **Imprimir atendimento** (num atendimento finalizado) abre o atendimento pronto para imprimir ou salvar em PDF, com o cabeçalho da clínica, a anamnese, os adendos e a linha de assinatura. Sem assinatura digital, a via impressa e assinada é o registro legal.
- No quadro **Documentos**, quem fez o atendimento emite:
  - **atestado** de **comparecimento** (data e horários, preenchidos a partir do agendamento) ou de **afastamento** (número de dias), com observações opcionais;
  - **receita** simples, um item por linha (medicamento, dose e como usar). Medicamentos controlados exigem os receituários oficiais, que o sistema não emite.
  - **pedido de exames**, um exame por linha, com a indicação clínica opcional.
- Um documento emitido não muda mais; ele fica guardado no prontuário e qualquer profissional pode imprimir de novo.

## Anexos
No quadro **Anexos**, qualquer profissional inclui arquivos no atendimento: resultados de exames, fotos, laudos. Só arquivos **PDF, JPG e PNG** de até **10 MB** (conferidos pelo conteúdo, não pelo nome). Eles abrem numa aba nova, só para profissionais. Resultados que chegam depois podem ser anexados também a um atendimento finalizado. Quem enviou um arquivo pode removê-lo enquanto o atendimento é rascunho; depois de finalizado, ele fica. Os anexos ficam guardados no banco de dados, então o backup diário inclui todos eles.

## Privacidade e guarda
- A **auditoria** registra quem criou, alterou, finalizou ou **abriu** cada atendimento, mas nunca copia o texto clínico.
- O prontuário é guardado por **20 anos** (Lei 13.787/2018): arquivar o paciente mantém o prontuário, e um paciente com prontuário não pode ser excluído definitivamente.
- A CID ainda não está disponível.

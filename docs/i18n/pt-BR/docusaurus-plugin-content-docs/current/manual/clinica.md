---
sidebar_position: 8
---

# Configurações da clínica

Estas telas são do **administrador da clínica**, no menu **Cadastros**.

## Configurações da clínica
Em **Cadastros > Configurações da clínica**: nome, CPF/CNPJ, e-mail e telefone da clínica, e o **horário da agenda** (início, fim e duração de cada horário).

A instalação atende **uma única clínica**, com um cadastro de pacientes, equipe, agenda e financeiro. Não há seletor de clínicas. A identificação interna da clínica é mantida para uma possível evolução futura.

A **área principal** define os tipos de atendimento quando a clínica é cadastrada. Em **Especialidades**, habilite só **Odontologia**, só **Medicina** ou as duas juntas (ou nenhuma, para outra área da saúde). As mesmas opções aparecem no formulário da clínica no painel do administrador do sistema. Alterar a área principal depois não modifica essas opções nem substitui os tipos de atendimento já existentes.

Odontologia habilita o odontograma e os dentes e faces dos itens de orçamento. Desativar preserva a consulta e a impressão dos itens dentários existentes, mas impede criar, alterar ou removê-los até habilitar novamente. Itens de orçamento gerais continuam disponíveis. Medicina prepara a configuração para extensões médicas; o prontuário comum continua disponível em qualquer área, conforme as permissões profissionais existentes. Habilitar um módulo não concede acesso ao prontuário nem cria automaticamente novos formulários de especialidade.

Em **Módulos** ficam as partes comuns às especialidades: **Agenda**, **Prontuário**, **Orçamentos**, **Financeiro**, **Rechamadas**, **Aniversariantes**, [**Convênios**](convenios.md) e [**Pessoal**](pessoal.md). Uma clínica nova começa com todos ligados, e uma instalação atualizada também. Um módulo desligado sai do menu, da tela inicial e da ficha do paciente para toda a equipe, inclusive para o administrador do sistema, e o endereço dele é recusado. Nada do que já foi registrado é apagado: religar mostra tudo de novo. **Orçamentos** e **Pessoal** precisam do **Financeiro** ligado, porque aprovar um orçamento cria a conta a receber e a folha do mês cria as contas a pagar. Pacientes, profissionais, equipe, tabelas base, configurações e auditoria estão sempre ligados.

Se algum agendamento futuro ficar fora do novo horário ou do novo intervalo, a mudança é recusada e a tela mostra qual. Ajuste esse agendamento antes.

## Tipos de atendimento
Em **Cadastros > Tipos de atendimento**: os tipos (cirurgia, consulta inicial…) e a cor que cada um pinta na agenda. Para deixar de usar um tipo sem perder o histórico, desmarque **ativo**.

## Auditoria
Em **Cadastros > Auditoria**: quem criou, alterou, excluiu ou abriu cada registro da clínica, quando, de qual endereço e o que mudou. Os filtros buscam por usuário, ação, tipo de registro e período. Os registros não podem ser alterados. Tentativas de entrada recusadas são apagadas depois de 30 dias.

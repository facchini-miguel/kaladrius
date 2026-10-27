# Visão geral

[🇺🇸 English](../en/overview.md) | 🇧🇷 Português | [🇪🇸 Español](../es/vision-general.md)

## O que é
Sistema de gestão de clínicas (odontológicas, médicas, de fisioterapia, psicologia etc.) com:
- uma **web** para a equipe da clínica (recepção, gestão, profissionais);
- um **app** (Android e iOS) para profissionais e pacientes.

## Público

| Quem | Onde usa | O que faz |
|---|---|---|
| Recepção / gestão da clínica | Web | Agenda, cadastros, rechamadas, relatórios, usuários |
| Profissional (dentista, médico…) | Web e app | Agenda própria, ficha do paciente |
| Paciente | App | Próprias consultas, solicitar horário, lembretes (fase 3) |
| Administrador da plataforma | Web (admin) | Clínicas, planos, suporte |

## Módulos (paridade com o sistema antigo)

1. **Pacientes:** pessoa física ou jurídica, documentos, endereço, contatos, observações. Busca por nome, código e CPF/CNPJ.
2. **Agenda:** grade semanal por profissional em slots configuráveis (padrão 30 min), com cor por tipo de atendimento, repetição semanal, bloqueio de conflito, e rechamadas e aniversariantes do dia em destaque.
3. **Rechamadas:** lembretes de retorno (paciente + data + descrição).
4. **Aniversariantes:** consulta por mês.
5. **Profissionais:** cadastro dos profissionais que atendem (antes "Dentistas").
6. **Tabelas base:** UF, cidades, bancos, estado civil, tipos de atendimento e cores.
7. **Usuários e permissões:** papéis por clínica com permissões de ver, criar, alterar e excluir por módulo. O administrador da clínica gerencia a equipe em Cadastros > Equipe (0.8.0).
8. **Novidades:** histórico de versões consultável no sistema e no app.
9. **Auditoria:** quem criou, alterou, excluiu ou consultou o quê e quando (LGPD).
10. **Idiomas:** português, inglês e espanhol, à escolha de cada usuário (0.13.0).
11. **Ajuda:** manual do usuário nos três idiomas dentro do sistema; documentação técnica só para o superusuário (0.14.0).
12. **Financeiro:** lançamentos a receber com parcelas, pagamentos com forma e conta, recibo, devedores (0.15.0). A pagar, fluxo de caixa e caixa do dia nas próximas versões.

## Modelo de negócio (em estudo)
- App **gratuito** nas lojas.
- Assinatura **paga** da web para as clínicas, com mais recursos.
- Por isso o sistema é **multi-clínica** desde o início.

## Fases

| Fase | Entrega |
|---|---|
| **1** ✅ | Web da equipe com paridade de funções + dados fictícios de teste + Docker local. Concluída na 0.7.0 e publicada no Google Cloud |
| Financeiro | Lançamentos a receber e a pagar, pagamentos, devedores, fluxo de caixa e caixa do dia (ver [plano-financeiro.md](plano-financeiro.md)) |
| 2 | API + app para profissionais e equipe |
| 3 | App para pacientes (login próprio, consultas, solicitação de horário, push) |
| 4 | Planos, cobrança, cadastro self-service da clínica, termos (lançamento comercial) |
| Futuro | Lembrete por WhatsApp, prontuário, orçamento e comissão, busca de endereço pelo CEP |

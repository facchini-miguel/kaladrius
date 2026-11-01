---
sidebar_position: 8
---

# Configurações da clínica

Estas telas são do **administrador da clínica**, no menu **Cadastros**.

## Configurações da clínica
Em **Cadastros > Configurações da clínica**: nome, documento (CPF/CNPJ no Brasil), e-mail e telefone da clínica, e o **horário da agenda** (início, fim e duração de cada horário).

A instalação atende **uma única clínica**, com um cadastro de pacientes, equipe, agenda e financeiro. Não há seletor de clínicas. A identificação interna da clínica é mantida para uma possível evolução futura.

A **área principal** define os tipos de atendimento quando a clínica é cadastrada. Em **Especialidades**, habilite só **Odontologia**, só **Medicina** ou as duas juntas (ou nenhuma, para outra área da saúde). As mesmas opções aparecem no formulário da clínica no painel do administrador do sistema. Alterar a área principal depois não modifica essas opções nem substitui os tipos de atendimento já existentes.

Odontologia habilita o odontograma e os dentes e faces dos itens de orçamento. Desativar preserva a consulta e a impressão dos itens dentários existentes, mas impede criar, alterar ou removê-los até habilitar novamente (o administrador do sistema ainda pode, com um aviso). Itens de orçamento gerais continuam disponíveis. Medicina prepara a configuração para extensões médicas; o prontuário comum continua disponível em qualquer área, conforme as permissões profissionais existentes. Habilitar um módulo não concede acesso ao prontuário nem cria automaticamente novos formulários de especialidade.

Em **Módulos** ficam as partes comuns às especialidades: **Agenda**, **Prontuário**, **Orçamentos**, **Financeiro**, **Rechamadas**, **Aniversariantes**, [**Convênios**](convenios.md) e [**Pessoal**](pessoal.md). Uma clínica nova começa com todos ligados, e uma instalação atualizada também. Um módulo desligado sai do menu, da tela inicial e da ficha do paciente para toda a equipe, e o endereço dele é recusado. O **administrador do sistema** continua vendo, marcado como **desligado** no menu e com um aviso nas telas dele, para manutenção ou para conhecer antes de ligar. Nada do que já foi registrado é apagado: religar mostra tudo de novo. **Orçamentos** e **Pessoal** precisam do **Financeiro** ligado, porque aprovar um orçamento cria a conta a receber e a folha do mês cria as contas a pagar. Pacientes, profissionais, equipe, tabelas base, configurações e auditoria estão sempre ligados.

Se algum agendamento futuro ficar fora do novo horário ou do novo intervalo, a mudança é recusada e a tela mostra qual. Ajuste esse agendamento antes.

**Exigir verificação em duas etapas de quem acessa o prontuário ou o financeiro** (vem ligada): profissionais com prontuário, administradores e o financeiro só usam o sistema depois de ativar o código do aplicativo autenticador (veja [Primeiros passos](inicio.md)); até lá, cada página leva ao QR code. A recepção não é obrigada, e os logins públicos da demonstração nunca são.

**País e fuso horário**: Brasil por padrão; também Estados Unidos, Reino Unido, Canadá, Austrália e África do Sul, e na América Latina México, Argentina, Chile, Colômbia, Peru, Uruguai, Paraguai, Bolívia e Equador. O país define os fusos oferecidos (a agenda e todos os horários seguem o da clínica, onde quer que cada pessoa esteja), os telefones no formato do país com o código certo do WhatsApp, os códigos postais (ZIP code, postcode…), a ordem das datas em inglês (10/31 nos Estados Unidos, 31/10 no Reino Unido, na Austrália e na África do Sul, 2026-10-31 no Canadá) os números e as datas em espanhol (1,234.56 no México e no Peru, 1.234,56 nos demais países latino-americanos) e a moeda sugerida, que acompanha a troca de país se nenhuma outra tiver sido escolhida. Fora do Brasil, o estado e a cidade do paciente são digitados, e RG e inscrição estadual não aparecem.

**Numeração dos dentes**: como os dentes aparecem no odontograma e nos orçamentos: **FDI** (11 a 48, dentes de leite 51 a 85), **Universal** (1 a 32 e A a T, usada nos Estados Unidos) ou **Palmer** (UR6, LL3, comum no Reino Unido). Começa com a do país (Universal nos Estados Unidos, FDI nos demais) e acompanha a troca de país se nenhuma outra tiver sido escolhida. Muda só a exibição: os dentes já registrados continuam os mesmos.

**Documentos de cada país**: pacientes, clínica, fornecedores e funcionários recebem os documentos do país da clínica, conferidos pelos dígitos verificadores e escritos do jeito do país (12-3456789, 943 476 5919, 20-12345678-6), e cada um mantém o nome oficial em todos os idiomas. Nas fichas de paciente e de fornecedor, o campo muda ao escolher pessoa física ou jurídica; quando um tipo não tem documento, o campo some. A clínica aceita o documento de pessoa física ou de empresa. O registro profissional continua livre, com os exemplos do país (CRO, CRM… no Brasil; GDC, GMC… no Reino Unido; NPI nos Estados Unidos).

| País | Paciente pessoa física | Empresa (paciente, fornecedor, clínica) | Fornecedor ou clínica pessoa física | Funcionário |
|---|---|---|---|---|
| Brasil | CPF | CNPJ | CPF | CPF |
| México | CURP | RFC | RFC | CURP |
| Argentina | DNI | CUIT | CUIT | DNI |
| Chile | RUT | RUT | RUT | RUT |
| Colômbia | Cédula de ciudadanía | NIT | NIT | Cédula de ciudadanía |
| Peru | DNI | RUC | RUC | DNI |
| Uruguai | Cédula de identidad | RUT | RUT | Cédula de identidad |
| Paraguai | Cédula de identidad | RUC | RUC | Cédula de identidad |
| Bolívia | Cédula de identidad | NIT | NIT | Cédula de identidad |
| Equador | Cédula | RUC | RUC | Cédula |
| Estados Unidos | — | EIN | EIN | SSN |
| Reino Unido | NHS number | Company number | — | National Insurance number |
| Canadá | Health card number | Business Number | Business Number | SIN |
| Austrália | Medicare number | ABN | ABN | — |
| África do Sul | ID number | Company registration number | — | ID number |

Nos Estados Unidos não se pede número nacional ao paciente, e na Austrália o tax file number dos funcionários não é guardado (a lei restringe quem pode guardá-lo). Se o país mudar, os documentos já salvos ficam como estão e são conferidos de novo ao editar.

**Moeda**: a moeda em que a clínica trabalha (real por padrão; também dólar americano, euro, libra esterlina e os pesos argentino, mexicano, chileno, colombiano e uruguaio, o guarani paraguaio, o sol peruano e o boliviano). Todos os valores do sistema, recibos inclusive, aparecem nela, para toda a equipe e em qualquer idioma que cada um use: o idioma só define os separadores (1.234,56 ou 1,234.56). Trocar a moeda **não converte** os valores já lançados; só muda como eles aparecem.

## Tipos de atendimento
Em **Cadastros > Tipos de atendimento**: os tipos (cirurgia, consulta inicial…) e a cor que cada um pinta na agenda. Para deixar de usar um tipo sem perder o histórico, desmarque **ativo**. Os tipos padrão (Cirurgia, Consulta inicial…) aparecem no idioma de cada pessoa; um tipo que a clínica cria ou renomeia aparece como foi digitado.

## Auditoria
Em **Cadastros > Auditoria**: quem criou, alterou, excluiu ou abriu cada registro da clínica, quando, de qual endereço e o que mudou. Os filtros buscam por usuário, ação, tipo de registro e período. Os registros não podem ser alterados. Tentativas de entrada recusadas são apagadas depois de 30 dias.

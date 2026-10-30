---
sidebar_position: 5
title: Primeiros passos
---

# Primeiros passos

Depois de instalar, o sistema tem só o **superusuário** criado pelo `criar_admin`. O superusuário é a conta de suporte da instalação: vê tudo da clínica e as páginas técnicas. A clínica é administrada pelo seu próprio **administrador**.

Uma instalação atende **uma clínica**. Para atender outra clínica, instale o sistema de novo (outro servidor, ou outro projeto do Compose no mesmo servidor).

## 1. Cadastre a clínica

1. Entre com o superusuário. No primeiro acesso, o sistema pede os dados da clínica: nome, **área principal** (Odontologia, Medicina ou outra área da saúde), as **especialidades** usadas (Odontologia, Medicina ou as duas) e, se quiser, CPF/CNPJ, e-mail, telefone e endereço.
2. Salve. A clínica já começa com **tipos de atendimento** (de dentista na Odontologia, gerais nas outras áreas) e **categorias e contas** do financeiro padrão, que a clínica pode alterar, e com todos os módulos comuns ligados. O horário da agenda (início, fim e duração de cada horário), as especialidades e os módulos ficam em **Cadastros > Configurações da clínica**.

## 2. Crie o administrador da clínica

Em **Cadastros > Equipe > Novo membro**, crie a pessoa com o perfil **Administrador**. Veja [Equipe](manual/equipe.md).

## 3. Entregue para a clínica

Daqui em diante, o administrador da clínica faz tudo dentro do sistema, sem o `/admin/`:

| Passo | Onde | Manual |
|---|---|---|
| Dados da clínica e horário da agenda | **Cadastros > Configurações da clínica** | [Configurações da clínica](manual/clinica.md) |
| Equipe (recepção, profissionais, administradores) | **Cadastros > Equipe** | [Equipe](manual/equipe.md) |
| Profissionais e as cores na agenda | **Cadastros > Profissionais** | [Equipe](manual/equipe.md) |
| Tipos de atendimento | **Cadastros > Tipos de atendimento** | [Configurações da clínica](manual/clinica.md) |
| Tabela de procedimentos | **Cadastros > Tabela de procedimentos** | [Orçamentos](manual/orcamentos.md) |
| Categorias e contas do financeiro | **Cadastros > Categorias** e **Cadastros > Contas** | [Financeiro](manual/financeiro.md) |

## Perfis

| Perfil | Pode |
|---|---|
| **Administrador** | Tudo na clínica: equipe, profissionais, configurações, contas a pagar, fluxo de caixa, relatórios, auditoria e pacientes arquivados |
| **Recepção** | Agenda de todos os profissionais, pacientes, orçamentos, rechamadas, recebimentos e caixa do dia |
| **Profissional** | Só a própria agenda, pacientes, orçamentos, rechamadas e o [prontuário](manual/prontuario.md); nenhum valor da clínica |

Os botões que a pessoa não pode usar não aparecem. Veja [Primeiros passos do manual](manual/inicio.md#perfis).

## Importar de outro sistema

O Kaladrius importa o banco do sistema PHP que ele substitui (`python manage.py importar_legado`). Para outros sistemas, a importação precisa ser escrita; veja [Como contribuir](contributing.md).

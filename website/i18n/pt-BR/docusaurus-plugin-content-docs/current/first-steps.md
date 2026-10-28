---
sidebar_position: 5
title: Primeiros passos
---

# Primeiros passos

Depois de instalar, o sistema tem só o **superusuário** criado pelo `criar_admin`. O superusuário é a conta de suporte da instalação: vê todas as clínicas e as páginas técnicas. Cada clínica é administrada pelo seu próprio **administrador**.

## 1. Crie a clínica

1. Entre com o superusuário e abra **`/admin/`** (administração do Django).
2. **Clínicas > Adicionar**: nome e, se quiser, CPF/CNPJ, e-mail, telefone e endereço. O horário da agenda (início, fim e duração de cada horário) pode ser mudado depois pela própria clínica.
3. Salve. A clínica já começa com **tipos de atendimento** e **categorias e contas** do financeiro padrão, que a clínica pode alterar.

## 2. Crie o administrador da clínica

1. **Usuários > Adicionar**: nome de usuário e senha.
2. Na página do usuário, em **Vínculos com clínicas**, adicione a clínica com o perfil **Administrador** e deixe **ativo** marcado.

Uma pessoa pode trabalhar em mais de uma clínica: adicione um vínculo para cada. No sistema, ela troca de clínica clicando no nome da clínica na barra superior.

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
| **Profissional** | Só a própria agenda, pacientes, orçamentos e rechamadas; nenhum valor da clínica |

Os botões que a pessoa não pode usar não aparecem. Veja [Primeiros passos do manual](manual/inicio.md#perfis).

## Importar de outro sistema

O Kaladrius importa o banco do sistema PHP que ele substitui (`python manage.py importar_legado`). Para outros sistemas, a importação precisa ser escrita; veja [Como contribuir](contributing.md).

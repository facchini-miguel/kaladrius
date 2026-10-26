# Modelo de dados (proposta da fase 1)

[🇺🇸 English](../en/data-model.md) | 🇧🇷 Português

## Princípio multi-clínica
- Toda informação de uma clínica tem uma chave `clinica`. Nenhuma consulta é feita sem filtrar pela clínica atual.
- O filtro é aplicado de forma centralizada (middleware + managers), não manualmente em cada tela.
- **Falha fechada:** todo modelo da clínica herda de `ModeloDaClinica` (`apps/core/isolamento.py`). O gerenciador padrão filtra pela clínica atual e, se não houver clínica definida, **dá erro em vez de mostrar dados**. Gravar ou excluir um registro de outra clínica também dá erro. Código da plataforma que precisa ver todas as clínicas (admin do Django, comandos) usa `sem_isolamento()` explicitamente.
- A clínica atual vem da sessão e só é aceita se o usuário tiver vínculo ativo com ela (ou for superusuário). O admin do Django é restrito aos superusuários da plataforma.
- Tabelas de referência públicas (UF, cidade, banco, estado civil) são **globais**, compartilhadas entre as clínicas.

## Entidades

### Plataforma
| Entidade | Campos principais | Observação |
|---|---|---|
| `Clinica` | nome, documento (CPF/CNPJ), contato, ativa, configurações da agenda (início, fim, duração do slot) | O "tenant" |
| `Usuario` | login, nome, e-mail, senha (Argon2), ativo | Usuário do Django |
| `Vinculo` | usuario, clinica, papel, ativo | Um usuário pode atuar em mais de uma clínica |

### Papéis e permissões (substitui `sist_pessoasgrupos` / `sist_modulosperm`)
| Papel | Equivale no sistema antigo | Acesso padrão |
|---|---|---|
| Superusuário da plataforma | MASTER | Tudo, em todas as clínicas |
| Administrador da clínica | ADMINISTRADOR | Tudo dentro da própria clínica |
| Recepção | — | Agenda, pacientes, rechamadas, aniversariantes |
| Profissional | — | A própria agenda e os pacientes |

Cada papel recebe as permissões `ver`, `criar`, `alterar` e `excluir` por módulo. A matriz fica em `apps/core/permissoes.py` e vale tanto no servidor (a requisição é bloqueada) quanto na tela (botões e menus somem). A revisão detalhada fica para depois da fase 1, como combinado.

| Módulo | Administrador | Recepção | Profissional |
|---|---|---|---|
| Pacientes | tudo | ver, criar, alterar | ver, criar, alterar |
| Agenda | tudo | tudo | ver, criar, alterar |
| Rechamadas | tudo | tudo | ver, criar, alterar |
| Aniversariantes | tudo | ver | ver |
| Profissionais | tudo | ver | ver |
| Tabelas base | tudo | ver | ver |
| Usuários da clínica | tudo | — | — |
| Configurações da clínica | tudo | — | — |

### Clínica
| Entidade | Campos principais | Sistema antigo |
|---|---|---|
| `Paciente` | clinica, tipo (PF/PJ), nome, razão social, CPF/CNPJ, RG, inscrição estadual, sexo, estado civil, nascimento, profissão, responsável, telefones (residencial, comercial, celular), e-mail, endereço (CEP, UF, cidade, bairro, logradouro, número, complemento), observações, ativo, datas de criação e alteração | `pessoas` |
| `Profissional` | clinica, nome, registro profissional (CRO/CRM…), cor, ativo, usuario (opcional) | `dentistas` |
| `TipoAtendimento` | clinica, nome, cor | `agenda_cor` (Cirurgia, Prótese…) |
| `Agendamento` | clinica, profissional, tipo, data, início, fim, paciente (opcional), descrição, série (repetição), criado por | `agendax` |
| `Rechamada` | clinica, paciente, data, descrição, concluída | `agenda` (is_rechamada) |

### Referência (globais)
`UF`, `Cidade` (fonte: IBGE), `Banco` (fonte: lista pública do Banco Central), `EstadoCivil`.

### Sistema
| Entidade | Uso |
|---|---|
| Releases | Lidas do arquivo `releases.yaml` (não ficam no banco). Veja [versionamento-e-releases.md](versionamento-e-releases.md) |
| `RegistroAuditoria` | Quem criou, alterou ou excluiu o quê e quando (LGPD) |

## Documentos e formatos
- CPF, CNPJ, telefones e CEP são guardados **sem pontuação** e formatados só na exibição (filtros em `apps/core/templatetags/formatos.py`).
- O CNPJ aceita o **formato alfanumérico** da Receita Federal (em vigor desde julho de 2026: letras nas 12 primeiras posições, dígitos verificadores numéricos). Validação em `apps/core/validadores.py`.
- O CPF/CNPJ é opcional (crianças, por exemplo), mas **único dentro da clínica** quando informado.

## Diferenças intencionais em relação ao sistema antigo
| Antes | Agora | Motivo |
|---|---|---|
| Dentista | Profissional | Sistema genérico |
| Cores fixas da agenda | Tipos de atendimento configuráveis por clínica | Cada especialidade tem os seus |
| Agendamento só com texto livre | Paciente **opcional** vinculado + descrição | Base para o app do paciente, sem perder o uso rápido |
| Tabelas de bairro e logradouro mantidas à mão | Endereço em campos de texto + UF e cidade da tabela do IBGE | Menos manutenção. A busca por CEP entra depois |
| Saldo, data de pagamento, banco, agência e conta no paciente | **Fora da fase 1** | Pertencem a um futuro módulo financeiro |
| MSN, homepage, fax | Removidos | Obsoletos |
| Datas `0000-00-00` | Campos opcionais (NULL) | Integridade |
| Sem chaves estrangeiras | Chaves estrangeiras e índices | Integridade e desempenho |

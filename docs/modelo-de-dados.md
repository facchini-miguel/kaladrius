# Modelo de dados (proposta da fase 1)

## Princípio multi-clínica
- Toda informação de uma clínica tem uma chave `clinica`. Nenhuma consulta é feita sem filtrar pela clínica atual.
- O filtro é aplicado de forma centralizada (middleware + managers), não manualmente em cada tela.
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

Cada papel recebe as permissões `ver`, `criar`, `alterar` e `excluir` por módulo. A revisão detalhada dessas permissões fica para depois da fase 1, como combinado.

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

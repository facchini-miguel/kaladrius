# Documentação do Medical System

[🇺🇸 English](../en/README.md) | 🇧🇷 Português | [🇪🇸 Español](../es/README.md)

| Documento | Conteúdo |
|---|---|
| [visao-geral.md](visao-geral.md) | O que o sistema faz, para quem, módulos e fases |
| [arquitetura.md](arquitetura.md) | Stack, repositórios, infraestrutura, segurança |
| [modelo-de-dados.md](modelo-de-dados.md) | Entidades, multi-clínica, relação com o sistema antigo |
| [plano-fase-1.md](plano-fase-1.md) | Plano detalhado da fase 1 (web + dados de teste) |
| [plano-financeiro.md](plano-financeiro.md) | Plano do módulo financeiro (a receber, a pagar, fluxo de caixa) |
| [versionamento-e-releases.md](versionamento-e-releases.md) | Como numeramos versões e registramos as novidades |
| [deploy.md](deploy.md) | Publicação no Google Cloud (free tier, IPv6), operação e backups |
| [sistema-legado.md](sistema-legado.md) | Resumo do sistema PHP antigo usado como referência |
| [decisoes/](decisoes/README.md) | Registro das decisões técnicas e de produto, com data e motivo |
| [manual/](manual/inicio.md) | Manual do usuário (também no sistema: **Ajuda > Manual do usuário**) |

## Convenções
- A documentação é escrita primeiro em **português** (`docs/pt-BR/`) e traduzida para o **inglês** (`docs/en/`) e o **espanhol** (`docs/es/`), com a mesma estrutura. Toda mudança atualiza os três idiomas no mesmo commit. O código usa nomes em **português para o domínio** (Paciente, Agendamento) e em inglês só no que é do framework.
- **Comentários e docstrings do código são escritos em inglês.** Os textos exibidos ao usuário (telas, mensagens, novidades) são escritos em português no código e traduzidos para inglês e espanhol em `locale/` (ver [arquitetura.md](arquitetura.md#idiomas-versão-0130-decisão-049)).
- Toda decisão importante vira um registro em `decisoes/`.
- Toda versão publicada ganha uma entrada em [`../../releases.yaml`](../../releases.yaml).

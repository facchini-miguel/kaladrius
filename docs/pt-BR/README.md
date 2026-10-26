# Documentação do Medical System

[🇺🇸 English](../en/README.md) | 🇧🇷 Português

| Documento | Conteúdo |
|---|---|
| [visao-geral.md](visao-geral.md) | O que o sistema faz, para quem, módulos e fases |
| [arquitetura.md](arquitetura.md) | Stack, repositórios, infraestrutura, segurança |
| [modelo-de-dados.md](modelo-de-dados.md) | Entidades, multi-clínica, relação com o sistema antigo |
| [plano-fase-1.md](plano-fase-1.md) | Plano detalhado da fase 1 (web + dados de teste) |
| [versionamento-e-releases.md](versionamento-e-releases.md) | Como numeramos versões e registramos as novidades |
| [sistema-legado.md](sistema-legado.md) | Resumo do sistema PHP antigo usado como referência |
| [decisoes/](decisoes/README.md) | Registro das decisões técnicas e de produto, com data e motivo |

## Convenções
- A documentação é escrita primeiro em **português** (`docs/pt-BR/`) e traduzida para o **inglês** (`docs/en/`), com a mesma estrutura. Toda mudança atualiza os dois idiomas no mesmo commit. O código usa nomes em **português para o domínio** (Paciente, Agendamento) e em inglês só no que é do framework.
- **Comentários e docstrings do código são escritos em inglês.** Os textos exibidos ao usuário (telas, mensagens, novidades) ficam em português.
- Toda decisão importante vira um registro em `decisoes/`.
- Toda versão publicada ganha uma entrada em [`../../releases.yaml`](../../releases.yaml).

# Versionamento e releases

## Número da versão: `MAIOR.MENOR.CORREÇÃO`

Seguimos o [Versionamento Semântico](https://semver.org/lang/pt-BR/):

| Parte | Quando aumenta | Exemplo |
|---|---|---|
| **MAIOR** | Mudança grande, que quebra compatibilidade (ex.: o app antigo deixa de funcionar com o servidor novo) | 1.4.7 → **2.0.0** |
| **MENOR** | **Recurso novo** ou melhoria relevante, compatível | 1.4.7 → **1.5.0** |
| **CORREÇÃO** | **Correção de bug** ou ajuste pequeno | 1.4.6 → **1.4.7** |

- Durante o desenvolvimento usamos `0.x.y`. A versão **1.0.0** é a primeira usada por uma clínica real.
- Quando o MENOR sobe, a CORREÇÃO volta a zero. Quando o MAIOR sobe, os dois voltam a zero.
- O app (`medical-system-app`) tem numeração própria e indica a versão mínima do servidor de que precisa.

## Onde ficam as novidades: `releases.yaml`

O arquivo [`../releases.yaml`](../releases.yaml) é a **única fonte** do histórico. Dele saem:
- a página **Novidades** dentro do sistema web;
- o endpoint da API que o app usa para mostrar "O que há de novo";
- o número da versão exibido no rodapé do sistema.

### Formato

```yaml
- versao: 1.5.0
  data: 2027-03-10
  titulo: Lembretes de retorno no app
  itens:
    - tipo: novo            # novo | melhoria | correcao | seguranca
      modulo: Rechamadas
      publico: [equipe, paciente]
      texto: >
        O paciente recebe no celular um aviso 7 dias antes da data de retorno.
        A clínica escolhe a mensagem em Configurações > Rechamadas.
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `versao` | sim | Número no formato `MAIOR.MENOR.CORREÇÃO` |
| `data` | sim | Data da publicação (AAAA-MM-DD) |
| `titulo` | não | Destaque da versão, numa frase |
| `itens[].tipo` | sim | `novo`, `melhoria`, `correcao` ou `seguranca` |
| `itens[].modulo` | sim | Área do sistema (Agenda, Pacientes…) |
| `itens[].publico` | sim | Quem vê o item: `equipe`, `paciente` ou ambos |
| `itens[].texto` | sim | **Poucas linhas**, em linguagem de usuário: o que mudou e como usar |

### Regras de escrita
- Escrever para o **usuário**, não para o programador. Por exemplo, "A agenda agora mostra…", e não "Refatorado o componente X".
- No máximo 3 linhas por item.
- Correções de segurança não descrevem a falha, só que foi corrigida.
- Itens só internos (infraestrutura, refatoração) não entram, ou entram com `publico: []`, e aí não aparecem para ninguém.
- Pacientes só veem itens com `paciente` em `publico`.

## Como aparece

**Web (equipe):** menu **Ajuda → Novidades**, com as versões da mais nova para a mais antiga, ícones por tipo (novo, melhoria, correção, segurança) e filtro por módulo. Depois de uma atualização, aparece um aviso "Versão X.Y.Z: veja o que mudou" até o usuário abrir.

**App:** tela **Novidades** no menu e, ao abrir uma versão nova pela primeira vez, um resumo "O que há de novo". Usa o endpoint:

```
GET /api/v1/releases?desde=1.4.0&publico=paciente
```

## Processo para publicar uma versão
1. Adicionar a entrada no topo de `releases.yaml` no mesmo pull request da mudança.
2. Atualizar a versão do projeto (`pyproject.toml`).
3. Criar a tag Git `vX.Y.Z` e a *Release* no GitHub, com o mesmo texto.
4. O CI valida o `releases.yaml` (formato, versão maior que a anterior, data) antes do deploy.

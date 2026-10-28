# Versionamento e releases

[🇺🇸 English](../en/versioning-and-releases.md) | 🇧🇷 Português | [🇪🇸 Español](../es/versionado-y-versiones.md)

## Número da versão: `MAIOR.MENOR.CORREÇÃO`

Seguimos o [Versionamento Semântico](https://semver.org/lang/pt-BR/):

| Parte | Quando aumenta | Exemplo |
|---|---|---|
| **MAIOR** | Mudança grande, que quebra compatibilidade (ex.: o app antigo deixa de funcionar com o servidor novo) | 1.4.7 → **2.0.0** |
| **MENOR** | **Recurso novo** ou melhoria relevante, compatível | 1.4.7 → **1.5.0** |
| **CORREÇÃO** | **Correção de bug** ou ajuste pequeno | 1.4.6 → **1.4.7** |

- Durante o desenvolvimento usamos `0.x.y`. A versão **1.0.0** é a primeira usada por uma clínica real.
- Quando o MENOR sobe, a CORREÇÃO volta a zero. Quando o MAIOR sobe, os dois voltam a zero.
- O app (`kaladrius-app`) tem numeração própria e indica a versão mínima do servidor de que precisa.

## Onde ficam as novidades: `releases.yaml`

O arquivo [`../../releases.yaml`](../../releases.yaml) é a **única fonte** do histórico. Dele saem:
- a página **Novidades** dentro do sistema web;
- o endpoint da API que o app usa para mostrar "O que há de novo";
- o número da versão exibido no rodapé do sistema;
- as *Releases* do GitHub, em inglês (comando `notas_release`).

### Formato

```yaml
- versao: 1.5.0
  data: 2027-03-10
  titulo:
    pt-br: Lembretes de retorno no app
    en: Recall reminders in the app
    es: Recordatorios de regreso en la app
  itens:
    - tipo: novo            # novo | melhoria | correcao | seguranca
      modulo: Rechamadas    # um dos nomes de MODULOS em apps/novidades/releases.py
      publico: [equipe, paciente]
      texto:
        pt-br: >
          O paciente recebe no celular um aviso 7 dias antes da data de retorno.
        en: >
          Patients get a notice on their phone 7 days before the recall date.
        es: >
          El paciente recibe en el celular un aviso 7 días antes de la fecha de regreso.
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `versao` | sim | Número no formato `MAIOR.MENOR.CORREÇÃO` |
| `data` | sim | Data da publicação (AAAA-MM-DD) |
| `titulo` | não | Destaque da versão, numa frase, nos três idiomas |
| `itens[].tipo` | sim | `novo`, `melhoria`, `correcao` ou `seguranca` |
| `itens[].modulo` | sim | Área do sistema (Agenda, Pacientes…), em português; a tela mostra a tradução |
| `itens[].publico` | sim | Quem vê o item: `equipe`, `paciente` ou ambos |
| `itens[].texto` | sim | **Poucas linhas**, em linguagem de usuário: o que mudou e como usar. Um texto por idioma (`pt-br`, `en`, `es`); um teste exige os três |

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
2. Atualizar a versão do projeto (`pyproject.toml`) e a linha "Versão atual" dos três READMEs. Os testes falham se algum deles ficar diferente do `releases.yaml`.
3. Criar a tag Git `vX.Y.Z` e a *Release* no GitHub **em inglês**, com o título e o texto gerados pelo comando:
   ```bash
   docker compose exec app python manage.py notas_release X.Y.Z --titulo   # título
   docker compose exec app python manage.py notas_release X.Y.Z            # texto
   ```
4. O CI valida o `releases.yaml` (formato, versão maior que a anterior, data, os três idiomas) antes do deploy.

O servidor lê o `releases.yaml` uma vez e guarda em memória. Em desenvolvimento, depois de editá-lo, reinicie o app (`docker compose restart app`).

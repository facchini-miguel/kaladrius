# Versioning and releases

🇺🇸 English | [🇧🇷 Português](../pt-BR/versionamento-e-releases.md)

## Version number: `MAJOR.MINOR.PATCH`

We follow [Semantic Versioning](https://semver.org/):

| Part | When it goes up | Example |
|---|---|---|
| **MAJOR** | Big, breaking change (e.g., the old app stops working with the new server) | 1.4.7 → **2.0.0** |
| **MINOR** | **New feature** or relevant compatible improvement | 1.4.7 → **1.5.0** |
| **PATCH** | **Bug fix** or small adjustment | 1.4.6 → **1.4.7** |

- During development we use `0.x.y`. Version **1.0.0** is the first one used by a real clinic.
- When MINOR goes up, PATCH resets to zero. When MAJOR goes up, both reset to zero.
- The app (`medical-system-app`) has its own numbering and declares the minimum server version it needs.

## Where release notes live: `releases.yaml`

[`../../releases.yaml`](../../releases.yaml) is the **single source** of the history. It feeds:
- the **What's new** page in the web app;
- the API endpoint the app uses to show "What's new";
- the version number shown in the footer.

Release note texts are written in **Portuguese**, since they are shown to Brazilian users. Field names stay in Portuguese, as in the file.

### Format

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

| Field | Required | Description |
|---|---|---|
| `versao` | yes | Version in `MAJOR.MINOR.PATCH` format |
| `data` | yes | Release date (YYYY-MM-DD) |
| `titulo` | no | One-sentence highlight of the version |
| `itens[].tipo` | yes | `novo` (new), `melhoria` (improvement), `correcao` (fix) or `seguranca` (security) |
| `itens[].modulo` | yes | Area of the system (Agenda, Pacientes…) |
| `itens[].publico` | yes | Who sees the item: `equipe` (staff), `paciente` (patient) or both |
| `itens[].texto` | yes | **A few lines**, in user language: what changed and how to use it |

### Writing rules
- Write for the **user**, not the developer. For example, "The schedule now shows…", not "Refactored component X".
- At most 3 lines per item.
- Security fixes do not describe the flaw, only that it was fixed.
- Internal-only items (infrastructure, refactoring) are left out, or added with `publico: []`, which hides them from everyone.
- Patients only see items with `paciente` in `publico`.

## How it is shown

**Web (staff):** **Help → What's new** menu, with versions from newest to oldest, icons by type (new, improvement, fix, security) and a module filter. After an update, a "Version X.Y.Z: see what changed" notice shows until the user opens it.

**App:** a **What's new** screen in the menu and, on first launch of a new version, a "What's new" summary. It uses the endpoint:

```
GET /api/v1/releases?desde=1.4.0&publico=paciente
```

## Publishing a version
1. Add the entry at the top of `releases.yaml` in the same pull request as the change.
2. Update the project version (`pyproject.toml`) and the "Current version" line in both READMEs. Tests fail if any of them differs from `releases.yaml`.
3. Create the Git tag `vX.Y.Z` and the GitHub *Release* with the same text.
4. CI validates `releases.yaml` (format, version greater than the previous one, date) before deploying.

The server reads `releases.yaml` once and keeps it in memory. In development, restart the app after editing it (`docker compose restart app`).

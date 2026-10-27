# Medical System documentation

🇺🇸 English | [🇧🇷 Português](../pt-BR/README.md)

| Document | Contents |
|---|---|
| [overview.md](overview.md) | What the system does, for whom, modules and phases |
| [architecture.md](architecture.md) | Stack, repositories, infrastructure, security |
| [data-model.md](data-model.md) | Entities, multi-tenancy, mapping from the legacy system |
| [phase-1-plan.md](phase-1-plan.md) | Detailed plan for phase 1 (web app + test data) |
| [financial-plan.md](financial-plan.md) | Financial module plan (receivables, payables, cash flow) |
| [versioning-and-releases.md](versioning-and-releases.md) | How versions are numbered and release notes are recorded |
| [deploy.md](deploy.md) | Google Cloud deployment (free tier, IPv6), operations and backups |
| [legacy-system.md](legacy-system.md) | Summary of the old PHP system used as reference |
| [decisions/](decisions/README.md) | Log of technical and product decisions, with date and reason |

## Conventions
- Documentation is written first in **Portuguese** (`docs/pt-BR/`) and translated into **English** (`docs/en/`), with the same structure. Every change updates both languages in the same commit.
- Code uses **Portuguese names for the domain** (Paciente, Agendamento) and English only for framework concepts.
- **Code comments and docstrings are written in English.** User-facing text (screens, messages, release notes) stays in Portuguese.
- Every important decision gets an entry in `decisions/`.
- Every published version gets an entry in [`../../releases.yaml`](../../releases.yaml).

## Glossary (domain terms kept in Portuguese in the code)

| Portuguese | English |
|---|---|
| Clínica | Clinic (tenant) |
| Paciente | Patient |
| Profissional | Practitioner (dentist, doctor…) |
| Agendamento / Agenda | Appointment / Schedule |
| Tipo de atendimento | Appointment type |
| Rechamada | Recall (follow-up reminder) |
| Aniversariantes | Birthdays |
| Vínculo | Membership (user ↔ clinic) |
| Novidades | What's new / release notes |

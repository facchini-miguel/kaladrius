# Decision log

🇺🇸 English | [🇧🇷 Português](../../pt-BR/decisoes/README.md)

Each row is a decision, with date and reason. If a decision changes, the old row is marked **superseded** and a new one is added, preserving the history.

| # | Date | Decision | Reason | Status |
|---|---|---|---|---|
| 001 | 2026-10-26 | Rewrite the Odonto System (PHP 5) from scratch | It does not run on current PHP and has serious security flaws | Accepted |
| 002 | 2026-10-26 | Back end and web in **Python + Django** | Built-in login, permissions and admin, secure by default, least effort to reach parity | Accepted |
| 003 | 2026-10-26 | API with **Django Ninja** | Modern (FastAPI-like) syntax inside Django, reusing models and permissions | Accepted |
| 004 | 2026-10-26 | App in **React Native + Expo** | One codebase for Android and iOS | Accepted |
| 005 | 2026-10-26 | **PostgreSQL 16** database in Docker | — | Accepted |
| 006 | 2026-10-26 | Everything in **Docker Compose on a Compute Engine VM**; no Cloud Run or Cloud SQL | Same environment locally and in production, no managed-service lock-in. Free tier (e2-micro) for testing | Accepted |
| 007 | 2026-10-26 | PHP and .NET ruled out | Owner's preference | Accepted |
| 008 | 2026-10-26 | **No migration of legacy data**; use fake test data | The old system is no longer in use | Accepted |
| 009 | 2026-10-26 | **Generic** system ("Practitioner" instead of "Dentist") | Serve any kind of clinic | Accepted |
| 010 | 2026-10-26 | Two **private** repositories: `medical-system` and `medical-system-app` | Independent life cycles and licenses | Accepted |
| 011 | 2026-10-26 | **Proprietary** license (all rights reserved), owned by Miguel Facchini (individual) | Keeps all future options open (AGPL, MIT, commercial) | Accepted |
| 012 | 2026-10-26 | **Multi-tenant** from phase 1 | Possible sale as a service (free app + paid web). Retrofitting later would be costly | Accepted (owner asked to proceed with the recommended default) |
| 013 | 2026-10-26 | Version history in `releases.yaml`, shown in the system and the app | Single source, versioned with the code | Accepted |
| 014 | 2026-10-26 | Semantic versioning, starting at 0.1.0 | Industry standard; 1.0.0 is the first real-world use | Accepted |
| 015 | 2026-10-26 | No GPL/AGPL dependencies | Keep the license choice open | Accepted |
| 016 | 2026-10-26 | Django 6.1 (current), move to 6.2 LTS in Apr/2027; Python 3.13 | Latest stable; LTS supported until 2030 | Accepted |
| 017 | 2026-10-26 | No Node build on the front end: Bootstrap 5.3 and HTMX 2 served as static files | Fewer tools to maintain | Accepted |
| 018 | 2026-10-26 | Bilingual docs: `docs/pt-BR/` (primary) and `docs/en/` (translation); `README.md` in English and `README.pt-BR.md` in Portuguese | Separate files per language avoid mixed text; English widens the audience if the project is opened | Accepted |
| 019 | 2026-10-26 | Code comments and docstrings in English; user-facing text in Portuguese | International standard for code, while keeping the users' language | Accepted |
| 020 | 2026-10-26 | Use **Google Cloud free tier resources only**: e2-micro in the US for production too, backups in US Cloud Storage, no snapshots; R$ 5 budget alert | Owner's request: zero cost | Accepted (supersedes the production part of 006: e2-small in São Paulo) |

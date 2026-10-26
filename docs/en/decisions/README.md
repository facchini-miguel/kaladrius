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
| 021 | 2026-10-26 | **Fail-closed** per-clinic isolation: the default manager filters by the current clinic and raises without one; explicit `sem_isolamento()` for platform code | A forgotten filter can never leak another clinic's data | Accepted |
| 022 | 2026-10-26 | Per-role permission matrix defined in code (`apps/core/permissoes.py`) | Simple and testable; review with the owner after phase 1 | Accepted |
| 023 | 2026-10-26 | Django admin restricted to platform superusers | The admin sees every clinic | Accepted |
| 024 | 2026-10-26 | Practitioners moved forward to step 2 | First clinic data; allows end-to-end isolation tests | Accepted |
| 025 | 2026-10-26 | Reference tables (states, IBGE municipalities, Banco Central banks) stored as JSON in the repository and loaded by migration; accent-insensitive search with PostgreSQL's `unaccent` extension | Official, versioned data reproducible in any environment, with no external API dependency | Accepted |
| 026 | 2026-10-26 | Per-clinic appointment types, with the 10 legacy types and colors created automatically for every new clinic | Parity with the legacy system, but editable per clinic | Accepted |
| 027 | 2026-10-26 | Each phase 1 step bumps the MINOR version (0.3.0, 0.4.0…); phase 1 ends at 0.7.0 | Steps add new features (semantic versioning rule) | Accepted |
| 028 | 2026-10-26 | Accept the alphanumeric CNPJ (IN RFB 2.229/2024) as well as the numeric one; documents and phones stored without punctuation | New CNPJs with letters have been issued since July 2026 | Accepted |
| 029 | 2026-10-26 | Schedule with FullCalendar 6 (MIT, free plugins only) and modal forms via HTMX | Ready-made, responsive week grid, no Node build | Accepted |
| 030 | 2026-10-26 | Overlap prevention also in the database: exclusion constraint with `btree_gist` | Enforces the rule even with simultaneous writes | Accepted |
| 031 | 2026-10-26 | Isolation filter decided when the query runs (`FiltroClinicaAtual` expression), not when it is built | Django builds form field querysets at import time; still fails closed on execution | Accepted (complements 021) |
| 032 | 2026-10-26 | Automatic audit via Django signals, with per-field before/after, patient record views and logins; passwords never stored | Accountability required by the LGPD for health data | Accepted |
| 033 | 2026-10-26 | django-axes (MIT): 5 wrong attempts per user + IP lock for 1 hour | Protection against password guessing | Accepted |
| 034 | 2026-10-26 | Test coverage measured in CI, minimum 90% | Keeps coverage from silently dropping | Accepted |
| 035 | 2026-10-26 | VM with **public IPv6 only** (no IPv4) | VM IPv4 is billed (US$ 0.005/h, free tier only 1 h/month); IPv6 is free. Requires IPv6 networks | Accepted (owner) |
| 036 | 2026-10-26 | Images in Artifact Registry, updates pulled by the VM every 5 min; CI authenticated with Workload Identity Federation | GitHub/GHCR have no IPv6; no stored keys | Accepted |
| 037 | 2026-10-26 | HTTPS by Caddy with Let's Encrypt and an sslip.io name | Valid certificate without buying a domain | Accepted |
| 038 | 2026-10-26 | Free domain `medical-system.duckdns.org` (AAAA only) and the VM's IPv6 reserved as static | Friendly name at no cost; the address never changes | Accepted (owner) |

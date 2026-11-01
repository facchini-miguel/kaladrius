# Security policy

Kaladrius stores patient data, so security reports get priority.

## Supported versions

Only the newest version receives fixes. Installations are expected to update (the Google
Cloud installation updates itself within 5 minutes of a release).

## Dependencies

Versions are pinned. GitHub's Dependabot alerts on known vulnerabilities in them and opens a
pull request with the fix as soon as an advisory is published; it also proposes new versions
weekly (Python and documentation packages) or monthly (GitHub Actions and Docker images), as
set in `.github/dependabot.yml`. Each pull request is reviewed and tested before it is merged.

## Reporting a vulnerability

Please **do not** open a public issue. Report it privately through
[GitHub Security Advisories](https://github.com/facchini-miguel/kaladrius/security/advisories/new),
with what you found, how to reproduce it and the version (shown in the footer of every page).

You will get an answer within 7 days. Once a fix is released, the advisory is published with
credit to you, unless you prefer otherwise.

## Scope

The code in this repository: the web app, the API, the Docker images and the deploy scripts.
How a clinic runs its own server (its passwords, firewall, backups) is the clinic's
responsibility; see [Security and privacy](https://kaladrius-docs.facchini.eti.br/security).

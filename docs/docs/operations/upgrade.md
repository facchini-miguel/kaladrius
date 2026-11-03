---
sidebar_position: 1
title: Upgrade
---

# Upgrade

Kaladrius follows [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH`. Each version is listed, with what changed, in **What's new** inside the system and in the [releases on GitHub](https://github.com/facchini-miguel/kaladrius/releases). Database migrations run by themselves when the app starts.

## Linux package

With the package repository (added by hand, or by the downloaded `.deb` or `.rpm` when installed), with the system's own updates: `sudo apt update && sudo apt upgrade`, `sudo dnf upgrade` or `sudo zypper update`. On Arch Linux and CachyOS, or without the repository, download the new version's package from the [releases page](https://github.com/facchini-miguel/kaladrius/releases) and install it over the installed one (`sudo apt install ./kaladrius_X.Y.Z-1_amd64.deb`, `sudo dnf install ./kaladrius-X.Y.Z-1.x86_64.rpm`). It has the same automatic rollback as the Google Cloud installation (below): a version that does not answer within 5 minutes is undone and the previous one keeps running; `sudo kaladrius estado` shows it. See [Linux package](../installation/linux-package.md#updates).

## Own server

```bash
cd /opt/kaladrius
sudo git pull                              # or: sudo git checkout v0.25.0
sudo docker build -t kaladrius:latest .
kaladrius up -d
kaladrius logs -f app                      # wait for "Booting worker", then Ctrl+C
```

Make a [backup](backup-restore.md) before upgrading; it is the only way back if something goes wrong.

## Google Cloud installation

Nothing to do: the VM installs every new image published by the CI within 5 minutes. To install now:

```bash
sudo /opt/kaladrius/bin/atualizar.sh --forcar
```

**Automatic rollback:** after starting a new version, the VM waits up to 5 minutes for the system to answer its health page (`/api/v1/saude`, with the database). If it does not, the VM puts back the version of the last successful update (kept as the `app:anterior` image) with its Compose file and Caddyfile, so a new Caddy or PostgreSQL image is undone too, records the new one as refused, so it is not installed again until a newer version is published, and the "automatic update" monitor reports the failure until then. `--forcar` tries the refused version again. A migration the new version already applied is not undone: when the previous version does not work with it, restore the backup.

## Going back to an earlier version

Migrations are not undone. An older version only works if the newer migrations are compatible with it (for example, they only added tables and columns). The safe way back is to restore the backup taken before the upgrade.

On your own server:

```bash
cd /opt/kaladrius
sudo git checkout v0.24.1
sudo docker build -t kaladrius:latest .
kaladrius up -d
```

On Google Cloud, stop the automatic updates first, or the VM goes back to the newest image within 5 minutes:

```bash
sudo systemctl stop kaladrius-atualizar.timer
cd /opt/kaladrius/release
sudo IMAGEM_APP=<registry>/app:0.24.1 docker compose -f docker-compose.prod.yml up -d app
# after the fix is published:
sudo systemctl start kaladrius-atualizar.timer
```

Every version has an image tag `X.Y.Z` that never changes.

---
sidebar_position: 1
title: Upgrade
---

# Upgrade

Kaladrius follows [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH`. Each version is listed, with what changed, in **What's new** inside the system and in the [releases on GitHub](https://github.com/facchini-miguel/kaladrius/releases). Database migrations run by themselves when the app starts.

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

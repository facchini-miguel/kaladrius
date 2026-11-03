---
sidebar_position: 2
title: Linux package (.deb, .rpm and Arch Linux)
---

# Linux package (.deb, .rpm and Arch Linux)

The simplest way to install Kaladrius on a server of the clinic or on a VPS: a package of the distribution, which installs Docker by itself and asks a few questions in text screens. No file to edit by hand.

## Supported systems

| System | Package | Docker |
|---|---|---|
| Debian 13 or newer, Ubuntu 24.04 or newer | `.deb` | from the distribution, installed with the package |
| Fedora, openSUSE Tumbleweed | `.rpm` | from the distribution, installed with the package |
| Arch Linux, CachyOS | `.pkg.tar.zst` (downloaded; not in the repository) | from the distribution, installed with the package. Rolling releases: good for trying Kaladrius out; for a clinic's server, prefer one of the systems above |
| Rocky Linux, AlmaLinux, Red Hat Enterprise Linux | `.rpm` | add [Docker's repository](https://docs.docker.com/engine/install/rhel/) first (below) |
| Debian 12, Ubuntu 22.04 | `.deb` | their Docker Compose is too old: install [Docker's own packages](https://docs.docker.com/engine/install/debian/) first |

Only 64-bit Intel and AMD processors (`amd64` / `x86_64`). The server needs ports **80** and **443** free: Kaladrius brings its own web server, Caddy, with HTTPS. When a firewall is on (firewalld on Fedora, Rocky, AlmaLinux and openSUSE; ufw on Ubuntu), `kaladrius configurar` opens both. Memory and disk: see [Requirements](requirements.md).

On Rocky Linux, AlmaLinux and Red Hat Enterprise Linux:

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
```

## Install

### From the package repository

With the package repository at [packages.facchini.eti.br](https://packages.facchini.eti.br) added, new versions of Kaladrius come with the system's own updates. On Debian and Ubuntu:

```bash
sudo apt install -y curl ca-certificates
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSLo /etc/apt/keyrings/facchini.asc https://packages.facchini.eti.br/chave.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/facchini.asc] https://packages.facchini.eti.br/deb stable main" | sudo tee /etc/apt/sources.list.d/facchini.list
sudo apt update
sudo apt install kaladrius
```

On Fedora, Rocky Linux, AlmaLinux and Red Hat Enterprise Linux:

```bash
sudo curl -fsSLo /etc/yum.repos.d/facchini.repo https://packages.facchini.eti.br/rpm/facchini.repo
sudo dnf install kaladrius
```

On openSUSE:

```bash
sudo zypper addrepo https://packages.facchini.eti.br/rpm/facchini.repo
sudo zypper install kaladrius
```

The repository and its `.rpm` packages are signed. Before trusting the key, `dnf` and `zypper` show its fingerprint, which must be `9D3A 0438 FF6C 00F9 1CA1 A0AB A5C3 35B2 EB36 7ABA`.

On Debian and Ubuntu the questions appear right away, in the server's language (Portuguese, Spanish or English). With `dnf` and `zypper`, run them yourself afterwards:

```bash
sudo kaladrius configurar
```

### From a downloaded package

On Arch Linux and CachyOS, which the repository does not serve, or to pick a version by hand:

1. Download the package of the newest version from the [releases page](https://github.com/facchini-miguel/kaladrius/releases/latest), with the `SHA256SUMS` file to check it. For example, for version 0.54.0:

   ```bash
   curl -fLO https://github.com/facchini-miguel/kaladrius/releases/download/v0.54.0/kaladrius_0.54.0-1_amd64.deb
   curl -fLO https://github.com/facchini-miguel/kaladrius/releases/download/v0.54.0/SHA256SUMS
   sha256sum --ignore-missing -c SHA256SUMS    # must say: OK
   ```

   On Fedora, openSUSE, Rocky and AlmaLinux the file is `kaladrius-0.54.0-1.x86_64.rpm`; on Arch Linux and CachyOS, `kaladrius-0.54.0-1-x86_64.pkg.tar.zst`.

2. Install it:

   ```bash
   sudo apt install ./kaladrius_0.54.0-1_amd64.deb       # Debian and Ubuntu
   sudo dnf install ./kaladrius-0.54.0-1.x86_64.rpm      # Fedora, Rocky, AlmaLinux
   sudo zypper install ./kaladrius-0.54.0-1.x86_64.rpm   # openSUSE
   sudo pacman -Syu && sudo pacman -U ./kaladrius-0.54.0-1-x86_64.pkg.tar.zst   # Arch Linux, CachyOS
   ```

   On Debian and Ubuntu the questions appear right away; with `dnf`, `zypper` and `pacman`, run `sudo kaladrius configurar` afterwards.

A downloaded package is not signed: `dnf` and `zypper` say so ("skipped OpenPGP checks", "unsigned rpm"). The `SHA256SUMS` check above is what proves the file is the one published.

## The questions

1. **How the clinic will reach Kaladrius**
   - **Only on the clinic's internal network:** no domain needed. The installer suggests this server's IP address on the network (for example `192.168.0.10`). That address must not change: reserve it for the server in the router (*DHCP reservation*), or give the server a fixed IP.
   - **Through the internet, with a domain:** the domain (for example `clinic.example.com`) must already point to this server, with ports 80 and 443 open to the internet, for the free Let's Encrypt certificate. The installer checks the domain in DNS and does not go on without it.
2. **The administrator:** the user name (`admin` by default), an optional e-mail and the password, typed twice. It needs at least 10 characters, not only digits, and not a common password; when the system refuses it, the screen says why and asks again. The password is not stored in any file.

Then the system is downloaded and started (a few minutes the first time), and the last screen shows the address to open in the browser. Log in with the administrator and follow [First steps](../first-steps.md): the clinic's details are filled in there.

To change the address later (a new IP, or moving from the internal network to a domain), run `sudo kaladrius configurar` again: passwords, keys and data stay.

## Internal network: the certificate

On the internal network the HTTPS certificate is issued by the installation itself, so until the clinic's computers trust it, the browser shows a security warning. Export the certificate once:

```bash
sudo kaladrius certificado        # saves kaladrius-certificado.crt in the current folder
```

Copy that file (on a USB stick, for example) to each of the clinic's computers and install it:

| On | How |
|---|---|
| Windows | double-click the file > **Install Certificate** > **Local Machine** > **Place all certificates in the following store** > **Trusted Root Certification Authorities** |
| macOS | double-click > **Keychain Access**, keychain **System**; then open the certificate, **Trust** > **Always Trust** |
| Linux | `sudo cp kaladrius-certificado.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates` |
| Firefox (any system) | **Settings** > **Privacy & Security** > **Certificates** > **View Certificates** > **Authorities** > **Import** |
| Android, iPhone | send the file to the device and open it; on the iPhone, then enable it in **Settings** > **General** > **About** > **Certificate Trust Settings** |

The certificate belongs to this installation only. It stays the same when the server's address changes, so it is installed once per computer.

## Installation by a technician (no questions)

With every option given and the administrator's password in `KALADRIUS_SENHA_ADMIN`, `configurar` asks nothing. `read -rs` keeps the password out of the shell's history:

```bash
sudo DEBIAN_FRONTEND=noninteractive apt install -y ./kaladrius_0.54.0-1_amd64.deb
read -rs KALADRIUS_SENHA_ADMIN && export KALADRIUS_SENHA_ADMIN
sudo --preserve-env=KALADRIUS_SENHA_ADMIN kaladrius configurar \
  --acesso rede-interna --endereco 192.168.0.10 --usuario admin --email ti@clinic.example
```

`--acesso` is `rede-interna` (internal network) or `internet`; for `internet`, `--endereco` is the domain. On an error (an invalid address, a refused password) it stops with the reason and a non-zero exit code.

## Everyday commands

| Command | What it does |
|---|---|
| `sudo kaladrius estado` | address, version and state of the services |
| `sudo kaladrius saude` | processor, memory, disk, the last backups and the scheduled tasks |
| `sudo kaladrius backup` | makes a backup now |
| `sudo kaladrius testar-restauracao` | restores the newest backup into a throwaway database and checks it |
| `sudo kaladrius certificado [FILE]` | the certificate for the internal network's computers |
| `sudo kaladrius senha [USER]` | changes a user's password (the administrator's by default) |
| `sudo kaladrius logs [app\|db\|caddy]` | the services' logs (Ctrl+C to leave) |
| `sudo kaladrius reiniciar` | restarts the services, applying changes to `/opt/kaladrius/.env` |
| `sudo kaladrius parar` / `iniciar` | stops or starts the system; the data stays |
| `kaladrius ajuda` | the list of commands |

## Backups

Every day at 06:00 UTC the database is saved to `/var/backups/kaladrius`, and the last 14 days are kept. Every Sunday the newest backup is restored into a throwaway database and checked. Each backup is recorded in the system: superusers see a warning at the top of every page when the last one is older than 26 hours.

:::warning
A backup on the same disk does not survive the loss of the disk. Copy `/var/backups/kaladrius` every day to another computer, an external disk or a cloud storage (for example with `rclone`). The files contain patient data: keep them private and encrypted.
:::

The folder and the number of days are `KALADRIUS_BACKUP_PASTA` and `KALADRIUS_BACKUP_DIAS` in `/opt/kaladrius/.env`. To restore a backup, see [Backup and restore](../operations/backup-restore.md#linux-package).

## Updates

Make a backup before (`sudo kaladrius backup`), then:

- **Installed from the repository:** `sudo apt update && sudo apt upgrade`, `sudo dnf upgrade` or `sudo zypper update`, like the rest of the system. A new version reaches the repository within an hour of its release.
- **From a downloaded package:** download the package of the new version and install it the same way (`sudo apt install ./kaladrius_….deb`, `sudo dnf install ./kaladrius-….rpm` or `sudo pacman -U ./kaladrius-….pkg.tar.zst`).

The system restarts on the new version; database migrations run by themselves.

**Automatic rollback:** if the new version does not answer within 5 minutes, the previous version is put back by itself, with its Compose file and Caddyfile, and keeps running, and `sudo kaladrius estado` shows the warning. `sudo kaladrius reiniciar`, `parar` and `iniciar` keep it on the previous version; installing the package again (`sudo apt install --reinstall kaladrius`, `sudo dnf reinstall kaladrius`, `sudo zypper install -f kaladrius`, or the downloaded file) tries the new one again.

## E-mail and monitoring (optional)

The `/opt/kaladrius/.env` file has the e-mail settings for password recovery (`DJANGO_EMAIL_*`, see [Configuration](../configuration.md)) and accepts the external monitor's addresses (`MONITOR_*_URL`, see [Monitoring](../operations/monitoring.md)). After editing it: `sudo kaladrius reiniciar`.

## Uninstall

```bash
sudo apt remove kaladrius                      # Debian, Ubuntu
sudo dnf remove --noautoremove kaladrius       # Fedora, Rocky, AlmaLinux
sudo zypper remove kaladrius                   # openSUSE
sudo pacman -R kaladrius                       # Arch Linux, CachyOS
```

The system stops, and **the data is kept**: the database (Docker volume `kaladrius_pgdata`), the backups in `/var/backups/kaladrius` and `/opt/kaladrius/.env`, with the database password. Installing the package again brings the system back with them. Without `--noautoremove`, dnf also removes Docker when it came with the package; the data stays, but installing again then needs the internet to download Docker. Deleting them is irreversible and is done by hand; the commands are shown when the package is removed.

To remove the package repository too: `sudo rm /etc/apt/sources.list.d/facchini.list /etc/apt/keyrings/facchini.asc` (Debian, Ubuntu), `sudo rm /etc/yum.repos.d/facchini.repo` (Fedora, Rocky, AlmaLinux) or `sudo zypper removerepo facchini` (openSUSE).

## Where things are

| Path | What |
|---|---|
| `/opt/kaladrius/.env` | the installation's settings and keys (readable by root only) |
| `/opt/kaladrius/release/` | the Compose file and the Caddyfile of the installed version |
| `/opt/kaladrius/bin/` | the `kaladrius` command and the server scripts |
| `/var/backups/kaladrius/` | the daily backups |
| `kaladrius-*.timer` (systemd) | backup, health samples every 5 minutes, weekly restore test |

# Linux package (decision 140)

The `.deb`, `.rpm` and Arch Linux `.pkg.tar.zst` of Kaladrius. The user guide is
[Linux package](https://kaladrius-docs.facchini.eti.br/installation/linux-package)
(`docs/docs/installation/linux-package.md`).

| File | What |
|---|---|
| `nfpm.yaml` | what goes into the packages, and their dependencies per format |
| `kaladrius` | the `kaladrius` command: `configure` (the text screens, or none with options) and the everyday tasks |
| `post_install.sh`, `pre_remove.sh`, `post_remove.sh` | the package's scripts: configure or update, stop, and never delete data |
| `repository/` | the apt source (`kaladrius.sources`, with the key) and the `.repo` file of the package repository at packages.facchini.eti.br (decision 142), which `post_install.sh` adds when it is not configured yet; the same files the site serves |
| `build.sh` | builds the packages into `dist/` with nFPM (a container pinned by digest) |
| `test_install.sh` | installs them in clean Debian, Ubuntu, Fedora, openSUSE and Arch Linux containers (CI, every push) |

The server scripts are those of `deploy/server/` (the Google Cloud ones): `common.sh` switches to
its package mode when the file `/opt/kaladrius/release/linux-package` exists. That file, written by
`build.sh`, holds the version and the public image (`ghcr.io/facchini-miguel/kaladrius:X.Y.Z@sha256:…`).

An update from 0.54 or earlier, whose names were Portuguese, is moved to the names of decision 147
by `post_install.sh` (`migrate_legacy_names` in `common.sh`): the state files, the `.env` variables
and the scheduled tasks. The old command names (`kaladrius configurar`, `--acesso rede-interna`…) still
work.

## Build

```bash
deploy/package/build.sh                             # the pyproject version and its published image
docker build -t kaladrius:test .                    # or: a local image, for a test
deploy/package/build.sh --image kaladrius:test [--version 0.99.0]
deploy/package/test_install.sh                      # dependencies resolve on each distribution
```

## Test in a virtual machine

The containers only check the dependencies. Before a change to the package or to the server
scripts, install it for real in a clean Debian 13 virtual machine (systemd and Docker inside),
for example the official cloud image
(`https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2`,
checked against its `SHA512SUMS`) under QEMU/KVM with cloud-init's NoCloud seed for an SSH
key. With a local image, load it first (`docker save kaladrius:test | ssh … docker load`) and
build the package with `--image kaladrius:test`. What to go through:

1. `sudo apt install ./kaladrius_….deb` in a terminal (the screens appear; `tmux` can drive
   them), and without one (the message to run `sudo kaladrius configure`).
2. A refused password (only digits; a common one), then a good one; the administrator logs in.
3. `curl --cacert` with the file of `sudo kaladrius certificate` reaches `https://<IP>/`.
4. `sudo kaladrius backup`, `sudo kaladrius test-restore`, a restore, the timers
   (`systemctl list-timers 'kaladrius-*'`: backup, health, restore test). The restore test
   passes with no clinic yet, passes with the system stopped (`sudo kaladrius stop`: it says
   it did not compare the clinics), and fails on a backup without the clinic once the system
   has one (create it, then test the older backup).
5. An update to a package of a newer version (`--version`), and one whose image does not start
   (the previous version comes back, `kaladrius status` warns; `sudo HEALTH_WAIT=60 apt
   install …` waits 60 seconds instead of 300). In that state, `sudo kaladrius configure` with
   another address restarts the previous version in seconds and never tries the refused one;
   backups and `kaladrius health` keep working. Then a good newer version: it comes up, and the
   previous and the refused images are gone from `docker image ls`.
6. `sudo apt remove kaladrius` (data kept) and installing it again (back with the data).
7. The technician's mode: every option and `KALADRIUS_ADMIN_PASSWORD`, with errors and without.
8. `sudo kaladrius configure` run again with the system running (no "another program uses
   port 80 or 443"), and after deleting `/opt/kaladrius/admin-created` with the same user name
   and another password: it says the user already exists, and the original password still
   logs in.
9. A first `sudo kaladrius configure` stopped after the address (no internet, or Ctrl+C at
   the password): `kaladrius status` says the setup did not finish, and installing the package
   again goes back to the questions (or the message to run `configure`) instead of starting a
   system with no administrator.
10. Without whiptail (openSUSE, Arch Linux: text mode), a password with a space at the start or
    the end logs in exactly as typed.
11. `sudo kaladrius certificate` with the system stopped fails with a message and leaves no
    empty file; `sudo kaladrius test-restore` before the first backup says so and does
    not fail.
12. The package repository: installing the downloaded package adds it (`apt update` then reads
    it), installing again does not duplicate it, `KALADRIUS_NO_REPOSITORY=1` leaves it out,
    and `sudo apt purge kaladrius` removes it (the data stays).
13. On Arch Linux or CachyOS, `sudo KALADRIUS_IMAGE=kaladrius:test pacman -U …` updates to
    that image (the update runs as its own systemd unit).
14. An update from a 0.54 package (Portuguese names) to this one: the timers become
    `kaladrius-health` and `kaladrius-restore-test`, `/opt/kaladrius/admin-criado` becomes
    `admin-created`, `.env` gets `KALADRIUS_ACCESS=internal-network` and `KALADRIUS_BACKUP_DIR`
    (the old file kept as `.env.before-147`), the rollback image is tagged `:previous`, and
    `sudo kaladrius estado` still works.

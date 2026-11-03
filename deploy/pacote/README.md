# Linux package (decision 140)

The `.deb`, `.rpm` and Arch Linux `.pkg.tar.zst` of Kaladrius. The user guide is
[Linux package](https://kaladrius-docs.facchini.eti.br/installation/linux-package)
(`docs/docs/installation/linux-package.md`).

| File | What |
|---|---|
| `nfpm.yaml` | what goes into the packages, and their dependencies per format |
| `kaladrius` | the `kaladrius` command: `configurar` (the text screens, or none with options) and the everyday tasks |
| `depois_de_instalar.sh`, `antes_de_remover.sh`, `depois_de_remover.sh` | the package's scripts: configure or update, stop, and never delete data |
| `gerar.sh` | builds both packages into `dist/` with nFPM (a container pinned by digest) |
| `testar_instalacao.sh` | installs them in clean Debian, Ubuntu, Fedora, openSUSE and Arch Linux containers (CI, every push) |

The server scripts are those of `deploy/servidor/` (the Google Cloud ones): `comum.sh` switches to
its package mode when the file `/opt/kaladrius/release/pacote-linux` exists. That file, written by `gerar.sh`,
holds the version and the public image (`ghcr.io/facchini-miguel/kaladrius:X.Y.Z@sha256:…`).

## Build

```bash
deploy/pacote/gerar.sh                              # the pyproject version and its published image
docker build -t kaladrius:teste .                   # or: a local image, for a test
deploy/pacote/gerar.sh --imagem kaladrius:teste [--versao 0.99.0]
deploy/pacote/testar_instalacao.sh                  # dependencies resolve on each distribution
```

## Test in a virtual machine

The containers only check the dependencies. Before a change to the package or to the server
scripts, install it for real in a clean Debian 13 virtual machine (systemd and Docker inside),
for example the official cloud image
(`https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2`,
checked against its `SHA512SUMS`) under QEMU/KVM with cloud-init's NoCloud seed for an SSH
key. With a local image, load it first (`docker save kaladrius:teste | ssh … docker load`) and
build the package with `--imagem kaladrius:teste`. What to go through:

1. `sudo apt install ./kaladrius_….deb` in a terminal (the screens appear; `tmux` can drive
   them), and without one (the message to run `sudo kaladrius configurar`).
2. A refused password (only digits; a common one), then a good one; the administrator logs in.
3. `curl --cacert` with the file of `sudo kaladrius certificado` reaches `https://<IP>/`.
4. `sudo kaladrius backup`, `sudo kaladrius testar-restauracao`, a restore, the timers
   (`systemctl list-timers 'kaladrius-*'`: backup, health, restore test). The restore test
   passes with no clinic yet, passes with the system stopped (`sudo kaladrius parar`: it says
   it did not compare the clinics), and fails on a backup without the clinic once the system
   has one (create it, then test the older backup).
5. An update to a package of a newer version (`--versao`), and one whose image does not start
   (the previous version comes back, `kaladrius estado` warns; `sudo SAUDE_ESPERA=60 apt
   install …` waits 60 seconds instead of 300). In that state, `sudo kaladrius configurar` with
   another address restarts the previous version in seconds and never tries the refused one;
   backups and `kaladrius saude` keep working. Then a good newer version: it comes up, and the
   previous and the refused images are gone from `docker image ls`.
6. `sudo apt remove kaladrius` (data kept) and installing it again (back with the data).
7. The technician's mode: every option and `KALADRIUS_SENHA_ADMIN`, with errors and without.
8. `sudo kaladrius configurar` run again with the system running (no "another program uses
   port 80 or 443"), and after deleting `/opt/kaladrius/admin-criado` with the same user name
   and another password: it says the user already exists, and the original password still
   logs in.

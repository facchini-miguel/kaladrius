#!/bin/sh
# After the package is installed or updated (.deb: "configure" [old version]; .rpm: 1 install,
# 2 update; Arch Linux: post_install or post_upgrade, with the new version). An installation
# whose setup did not finish (no .env, or no administrator yet) is configured with `kaladrius
# configure`; an update, or installing again after a removal, starts the system on the image of
# the package's version, with the automatic rollback of update.sh (decision 135). --force:
# installing a package is always deliberate, and the image may be the one already recorded (the
# containers stopped with the removal).
set -e
DIR=/opt/kaladrius
ETC=/etc
# The variables a person may give (the old names of decision 147 still work).
KALADRIUS_IMAGE=${KALADRIUS_IMAGE:-${KALADRIUS_IMAGEM:-}}
HEALTH_WAIT=${HEALTH_WAIT:-${SAUDE_ESPERA:-}}
KALADRIUS_NO_REPOSITORY=${KALADRIUS_NO_REPOSITORY:-${KALADRIUS_SEM_REPOSITORIO:-}}

# An update from 0.54 or earlier: the state files, the .env variables and the scheduled tasks
# under their names of decision 147, before anything below reads them.
bash -c '. "$0" && migrate_legacy_names' "$DIR/bin/common.sh" \
  || echo "Kaladrius: the names of an older version could not all be updated."
mkdir -p "$DIR/health"
ln -sfn ../.env "$DIR/release/.env"
systemctl daemon-reload >/dev/null 2>&1 || true

# The package repository (decision 142), like Google Chrome's and VS Code's packages: a server
# installed from a downloaded .deb or .rpm then gets new versions with the system's own updates.
# Added only when the repository is not configured yet (by hand, in any file, or by an earlier
# installation, whose file is left as it is); never on Arch Linux. KALADRIUS_NO_REPOSITORY=1
# (a technician's choice) leaves it out, now and on later installations.
add_repository() {
  case "${1:-}" in
    configure) source_file=kaladrius.sources target=$ETC/apt/sources.list.d ;;
    1 | 2)
      source_file=kaladrius.repo
      if [ -d "$ETC/zypp/repos.d" ]; then target=$ETC/zypp/repos.d; else target=$ETC/yum.repos.d; fi ;;
    *) return 0 ;;
  esac
  [ "${KALADRIUS_NO_REPOSITORY:-}" = 1 ] && touch "$DIR/no-repository"
  [ -e "$DIR/no-repository" ] && return 0
  [ -d "$target" ] || return 0
  [ -e "$target/$source_file" ] && return 0
  grep -qsF packages.facchini.eti.br/kaladrius "$target"/* && return 0
  install -m 0644 "$DIR/repository/$source_file" "$target/$source_file" || return 1
  echo "Kaladrius: repositório de pacotes adicionado / repositorio de paquetes añadido / package repository added: $target/$source_file"
}
add_repository "${1:-}" || echo "Kaladrius: the package repository was not added."

# A first `configure` that stopped after writing .env (no internet, say) left no administrator:
# starting the system alone would leave the clinic with no account to log in, so it goes to the
# questions below, which `configure` asks again with the earlier answers as defaults.
if [ -f "$DIR/.env" ] && [ -f "$DIR/admin-created" ]; then
  # The scheduled tasks first (a removal disabled them; update.sh enables them only once the
  # new version is running): the backups go on, and warn, even when it does not come up below.
  systemctl enable --now kaladrius-backup.timer kaladrius-health.timer \
    kaladrius-restore-test.timer >/dev/null 2>&1 || true
  # Docker itself: Docker's own package (docker-ce: Rocky, AlmaLinux, RHEL) does not start it
  # when installed, and dnf removes it with this package, so installing again after a removal
  # brings it back stopped.
  systemctl enable --now docker >/dev/null 2>&1 || true
  echo "Kaladrius: updating the system to the package's version..."
  # pacman (Arch Linux, CachyOS: the version as $1) may run this in a sandbox with no network
  # (CachyOS's does), where the health check of update.sh never reaches the system and every
  # update would be rolled back: there the update runs as its own systemd unit, outside it, and
  # this waits for it and shows its output. The unit starts with a clean environment: the
  # variables update.sh reads go along.
  case "${1:-}" in
    [0-9]*.*-*)
      set -- systemd-run --quiet --wait --pipe --collect --unit=kaladrius-package-update \
        ${HEALTH_WAIT:+"--setenv=HEALTH_WAIT=$HEALTH_WAIT"} \
        ${KALADRIUS_IMAGE:+"--setenv=KALADRIUS_IMAGE=$KALADRIUS_IMAGE"} ;;
    *) set -- ;;
  esac
  "$@" "$DIR/bin/update.sh" --force </dev/null \
    || echo "Kaladrius: the new version did not come up (see: sudo kaladrius status)."
  exit 0
fi

# Not configured yet (a first installation, one removed before it was configured, or a setup
# that did not finish): on Debian and Ubuntu, with apt in a terminal, the questions come right
# away, like debconf's. dnf runs its scriptlets without a terminal, so on the .rpm the message
# below says what to run.
if [ "${1:-}" = configure ] && [ "${DEBIAN_FRONTEND:-}" != noninteractive ] \
  && [ -t 1 ] && (exec </dev/tty) 2>/dev/null; then
  kaladrius configure </dev/tty >/dev/tty 2>/dev/tty && exit 0
fi
cat <<'TEXT'

  Kaladrius instalado. Para terminar a instalação / Para terminar la instalación /
  To finish the installation:

      sudo kaladrius configure

TEXT

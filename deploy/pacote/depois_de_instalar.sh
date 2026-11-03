#!/bin/sh
# After the package is installed or updated (.deb: "configure" [old version]; .rpm: 1 install,
# 2 update; Arch Linux: post_install or post_upgrade, with the new version). An installation
# whose setup did not finish (no .env, or no administrator yet) is configured with `kaladrius
# configurar`; an update, or installing again after a removal, starts the system on the image of
# the package's version, with the automatic rollback of atualizar.sh (decision 135). --forcar:
# installing a package is always deliberate, and the image may be the one already recorded (the
# containers stopped with the removal).
set -e
DIR=/opt/kaladrius
mkdir -p "$DIR/saude"
ln -sfn ../.env "$DIR/release/.env"
systemctl daemon-reload >/dev/null 2>&1 || true

# A first `configurar` that stopped after writing .env (no internet, say) left no administrator:
# starting the system alone would leave the clinic with no account to log in, so it goes to the
# questions below, which `configurar` asks again with the earlier answers as defaults.
if [ -f "$DIR/.env" ] && [ -f "$DIR/admin-criado" ]; then
  # The scheduled tasks first (a removal disabled them; atualizar.sh enables them only once the
  # new version is running): the backups go on, and warn, even when it does not come up below.
  systemctl enable --now kaladrius-backup.timer kaladrius-saude.timer \
    kaladrius-restauracao.timer >/dev/null 2>&1 || true
  # Docker itself: Docker's own package (docker-ce: Rocky, AlmaLinux, RHEL) does not start it
  # when installed, and dnf removes it with this package, so installing again after a removal
  # brings it back stopped.
  systemctl enable --now docker >/dev/null 2>&1 || true
  echo "Kaladrius: atualizando o sistema para a versão do pacote..."
  # pacman (Arch Linux, CachyOS: the version as $1) may run this in a sandbox with no network
  # (CachyOS's does), where the health check of atualizar.sh never reaches the system and every
  # update would be rolled back: there the update runs as its own systemd unit, outside it, and
  # this waits for it and shows its output. The unit starts with a clean environment: the
  # variables atualizar.sh reads go along.
  case "${1:-}" in
    [0-9]*.*-*)
      set -- systemd-run --quiet --wait --pipe --collect --unit=kaladrius-atualizar-pacote \
        ${SAUDE_ESPERA:+"--setenv=SAUDE_ESPERA=$SAUDE_ESPERA"} \
        ${KALADRIUS_IMAGEM:+"--setenv=KALADRIUS_IMAGEM=$KALADRIUS_IMAGEM"} ;;
    *) set -- ;;
  esac
  "$@" "$DIR/bin/atualizar.sh" --forcar </dev/null \
    || echo "Kaladrius: a versão nova não entrou no ar (veja: sudo kaladrius estado)."
  exit 0
fi

# Not configured yet (a first installation, one removed before it was configured, or a setup
# that did not finish): on Debian and Ubuntu, with apt in a terminal, the questions come right
# away, like debconf's. dnf runs its scriptlets without a terminal, so on the .rpm the message
# below says what to run.
if [ "${1:-}" = configure ] && [ "${DEBIAN_FRONTEND:-}" != noninteractive ] \
  && [ -t 1 ] && (exec </dev/tty) 2>/dev/null; then
  kaladrius configurar </dev/tty >/dev/tty 2>/dev/tty && exit 0
fi
cat <<'TEXTO'

  Kaladrius instalado. Para terminar a instalação / Para terminar la instalación /
  To finish the installation:

      sudo kaladrius configurar

TEXTO

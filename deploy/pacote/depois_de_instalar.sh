#!/bin/sh
# After the package is installed or updated (.deb: "configure" [old version]; .rpm: 1 install,
# 2 update). An installation without .env is configured with `kaladrius configurar`; an
# update, or installing again after a removal, starts the system on the image of the package's version, with the automatic rollback of
# atualizar.sh (decision 135). --forcar: installing a package is always deliberate, and the
# image may be the one already recorded (the containers stopped with the removal).
set -e
DIR=/opt/kaladrius
mkdir -p "$DIR/saude"
ln -sfn ../.env "$DIR/release/.env"
systemctl daemon-reload >/dev/null 2>&1 || true

if [ -f "$DIR/.env" ]; then
  echo "Kaladrius: atualizando o sistema para a versão do pacote..."
  "$DIR/bin/atualizar.sh" --forcar </dev/null \
    || echo "Kaladrius: a versão nova não entrou no ar e o sistema segue na anterior (sudo kaladrius estado)."
  exit 0
fi

# Not configured yet (a first installation, or one removed before it was configured): on Debian
# and Ubuntu, with apt in a terminal, the questions come right away, like debconf's. dnf runs
# its scriptlets without a terminal, so on the .rpm the message below says what to run.
if [ "${1:-}" = configure ] && [ "${DEBIAN_FRONTEND:-}" != noninteractive ] \
  && [ -t 1 ] && (exec </dev/tty) 2>/dev/null; then
  kaladrius configurar </dev/tty >/dev/tty 2>/dev/tty && exit 0
fi
cat <<'TEXTO'

  Kaladrius instalado. Para terminar a instalação / Para terminar la instalación /
  To finish the installation:

      sudo kaladrius configurar

TEXTO

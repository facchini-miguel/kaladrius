#!/bin/bash
# Installs the packages of dist/ (deploy/pacote/gerar.sh) in clean containers of each supported
# family, with the Docker of each distribution's own repositories, and checks the command and
# Docker Compose are there: catches a dependency a distribution cannot satisfy. Run by CI on
# every push (ci.yml); the full installation (systemd, the system running, backups, updates)
# is tested in a virtual machine, see deploy/pacote/README.md. The images are only throwaway
# test containers with no credentials, so they follow their tags.
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSAO=$(sed -n 's/^VERSAO=//p' dist/pacote-linux)
DEB=kaladrius_${VERSAO}-1_amd64.deb
RPM=kaladrius-${VERSAO}-1.x86_64.rpm
CONFERIR='kaladrius versao && docker compose version && test -x /opt/kaladrius/bin/atualizar.sh'

instalar() {  # instalar IMAGE COMMAND
  echo "== $1"
  docker run --rm -v "$PWD/dist:/dist:ro" "$1" sh -c "$2 && $CONFERIR"
}

instalar debian:13 "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /dist/$DEB >/dev/null"
instalar ubuntu:24.04 "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /dist/$DEB >/dev/null"
instalar fedora:43 "dnf -y -q install /dist/$RPM >/dev/null"
instalar opensuse/tumbleweed "zypper -q -n --no-gpg-checks install --allow-unsigned-rpm /dist/$RPM >/dev/null"
echo "Instalação conferida em todas as distribuições."

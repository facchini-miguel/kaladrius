#!/bin/sh
# Before the package is removed (.deb: "remove"; .rpm: 0; Arch Linux: the version removed, as
# pacman runs pre_remove only on a removal). An update (.deb "upgrade", .rpm 1; pacman runs
# pre_upgrade instead) changes nothing here. The system stops; its data stays (see
# depois_de_remover.sh).
set -e
case "${1:-}" in
  remove | 0 | [0-9]*.*-*) ;;
  *) exit 0 ;;
esac
systemctl disable --now kaladrius-backup.timer kaladrius-saude.timer \
  kaladrius-restauracao.timer >/dev/null 2>&1 || true
if [ -f /opt/kaladrius/.env ] && command -v docker >/dev/null; then
  docker compose -f /opt/kaladrius/release/docker-compose.prod.yml down || true
fi

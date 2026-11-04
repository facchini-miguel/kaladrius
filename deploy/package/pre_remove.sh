#!/bin/sh
# Before the package is removed (.deb: "remove"; .rpm: 0; Arch Linux: the version removed, as
# pacman runs pre_remove only on a removal). An update (.deb "upgrade", .rpm 1; pacman runs
# pre_upgrade instead) changes nothing here. The system stops; its data stays (see
# post_remove.sh).
set -e
case "${1:-}" in
  remove | 0 | [0-9]*.*-*) ;;
  *) exit 0 ;;
esac
systemctl disable --now kaladrius-backup.timer kaladrius-health.timer \
  kaladrius-restore-test.timer >/dev/null 2>&1 || true
if [ -f /opt/kaladrius/.env ] && command -v docker >/dev/null; then
  # Through common.sh: after a rollback, with the Compose file of the version running.
  bash -c 'source /opt/kaladrius/bin/common.sh && compose down' || true
fi

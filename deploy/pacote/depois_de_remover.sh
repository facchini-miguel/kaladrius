#!/bin/sh
# After the package is removed. The patients' data is never deleted by the package: the
# database (Docker volume kaladrius_pgdata), the backups and the .env with its passwords stay,
# and only a person decides to delete them, with the commands below.
set -e
systemctl daemon-reload >/dev/null 2>&1 || true
case "${1:-}" in
  remove | purge | 0) ;;
  *) exit 0 ;;
esac
rm -f /opt/kaladrius/release/.env
cat <<'TEXTO'

  Kaladrius removido. Os dados foram mantidos / Los datos se mantuvieron / The data was kept:
    /opt/kaladrius/.env, /var/backups/kaladrius, volume Docker kaladrius_pgdata

  Para apagar tudo / Para borrar todo / To delete everything (irreversível / irreversible):
    sudo docker volume rm kaladrius_pgdata kaladrius_caddy_data kaladrius_caddy_config
    sudo rm -r /opt/kaladrius /var/backups/kaladrius

TEXTO

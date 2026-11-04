#!/bin/sh
# After the package is removed. The patients' data is never deleted by the package: the
# database (Docker volume kaladrius_pgdata), the backups and the .env with its passwords stay,
# and only a person decides to delete them, with the commands below.
# .deb: "remove" or "purge"; .rpm: 0; Arch Linux: the version removed (pacman runs post_remove
# only on a removal).
set -e
ETC=/etc
systemctl daemon-reload >/dev/null 2>&1 || true
case "${1:-}" in
  remove | purge | 0 | [0-9]*.*-*) ;;
  *) exit 0 ;;
esac
rm -f /opt/kaladrius/release/.env
# The package repository stays, so `apt install kaladrius` (or dnf, zypper) brings it back with
# the data; purging the .deb removes it.
if [ "${1:-}" = purge ]; then
  rm -f "$ETC/apt/sources.list.d/kaladrius.sources"
fi
cat <<'TEXT'

  Kaladrius removido. Os dados foram mantidos / Los datos se mantuvieron / The data was kept:
    /opt/kaladrius/.env, /var/backups/kaladrius, volume Docker kaladrius_pgdata

  Para apagar tudo / Para borrar todo / To delete everything (irreversível / irreversible):
    sudo docker volume rm kaladrius_pgdata kaladrius_caddy_data kaladrius_caddy_config
    sudo rm -r /opt/kaladrius /var/backups/kaladrius

TEXT
for file in "$ETC/apt/sources.list.d/kaladrius.sources" "$ETC/yum.repos.d/kaladrius.repo" \
  "$ETC/zypp/repos.d/kaladrius.repo"; do
  if [ -e "$file" ]; then
    printf '  %s\n    sudo rm %s\n\n' "Repositório de pacotes / Repositorio de paquetes / Package repository:" "$file"
  fi
done

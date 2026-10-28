#!/bin/bash
# One-time move of a server installed before 0.26.1 from the "medical-system" names to
# "kaladrius" (decision 071): folder, systemd units, Compose project and volumes. The system
# is offline for about a minute. The old volumes stay as a copy until removed by hand:
#   docker volume rm medical-system_pgdata medical-system_caddy_data medical-system_caddy_config
# Run as root, with the new image already pulled (the update timer does it every 5 minutes):
#   docker run --rm --entrypoint cat <app image> /app/deploy/servidor/migrar_para_kaladrius.sh | sudo bash
set -euo pipefail
ANTIGO=/opt/medical-system
NOVO=/opt/kaladrius
IMAGEM_APP=us-east1-docker.pkg.dev/medical-system-facchini/kaladrius/app:latest

if [ -e "$NOVO" ]; then
  echo "Nada a fazer: $NOVO já existe."
  exit 0
fi
if [ ! -d "$ANTIGO" ]; then
  echo "Nada a migrar: $ANTIGO não existe."
  exit 1
fi

echo "== Parando os agendamentos e o sistema"
systemctl stop medical-system-atualizar.timer medical-system-backup.timer \
  medical-system-saude.timer medical-system-atualizar.service medical-system-backup.service \
  medical-system-saude.service 2>/dev/null || true
docker compose -p medical-system -f "$ANTIGO/release/docker-compose.prod.yml" down

echo "== $ANTIGO -> $NOVO"
mv "$ANTIGO" "$NOVO"

echo "== Copiando os volumes (os antigos ficam como cópia)"
for volume in pgdata caddy_data caddy_config; do
  docker volume create "kaladrius_$volume" >/dev/null
  docker run --rm --entrypoint sh -v "medical-system_$volume:/de:ro" \
    -v "kaladrius_$volume:/para" postgres:16-alpine -c 'cp -a /de/. /para/'
done

echo "== Trocando os agendamentos do systemd"
systemctl disable medical-system-atualizar.timer medical-system-backup.timer \
  medical-system-saude.timer 2>/dev/null || true
mkdir -p "$NOVO/unidades-antigas"
mv /etc/systemd/system/medical-system-* "$NOVO/unidades-antigas/" 2>/dev/null || true
systemctl daemon-reload

echo "== Subindo o sistema com os nomes novos"
export MIGRANDO=1
# shellcheck source=/dev/null
source /dev/stdin <<<"$(docker run --rm --entrypoint cat "$IMAGEM_APP" /app/deploy/servidor/comum.sh)"
rm -f "$IMAGEM_INSTALADA"
extrair_arquivos_de_deploy
"$DIR/bin/atualizar.sh" --forcar
systemctl list-timers 'kaladrius-*' --no-pager
echo "Migração concluída."

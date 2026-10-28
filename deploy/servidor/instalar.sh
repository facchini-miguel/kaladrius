#!/bin/bash
# VM startup script (runs as root on every boot; safe to run again).
# Installs Docker, adds swap, installs the systemd timers and starts the stack.
set -euo pipefail
exec > >(tee -a /var/log/medical-system-instalar.log) 2>&1
echo "== $(date -u) instalar.sh"

# 1 GB of swap: the e2-micro has only 1 GB of RAM.
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
swapon -a

if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  apt-get update -q
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io docker-compose curl
fi
systemctl enable --now docker

DIR=/opt/medical-system
REGISTRO=us-east1-docker.pkg.dev
IMAGEM_APP="$REGISTRO/medical-system-facchini/kaladrius/app:latest"
mkdir -p "$DIR"
token=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "$token" | docker login -u oauth2accesstoken --password-stdin "https://$REGISTRO" >/dev/null
if ! docker pull -q "$IMAGEM_APP" >/dev/null; then
  echo "Imagem ainda não publicada no Artifact Registry; tentarei de novo no próximo boot."
  exit 0
fi

# The rest of the deploy files (and the newest version of the scripts) come from the image.
source /dev/stdin <<<"$(docker run --rm --entrypoint cat "$IMAGEM_APP" /app/deploy/servidor/comum.sh)"
extrair_arquivos_de_deploy

instalar_agendamentos
"$DIR/bin/atualizar.sh" --forcar

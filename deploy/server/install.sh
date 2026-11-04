#!/bin/bash
# VM startup script (runs as root on every boot; safe to run again).
# Installs Docker, adds swap, installs the systemd timers and starts the stack.
set -euo pipefail
exec > >(tee -a /var/log/kaladrius-install.log) 2>&1
echo "== $(date -u) install.sh"

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

DIR=/opt/kaladrius
REGISTRY=us-east1-docker.pkg.dev
APP_IMAGE="$REGISTRY/medical-system-facchini/kaladrius/app:latest"
# A server installed before 0.26.1 must be migrated first (see common.sh).
if [ -d /opt/medical-system ] && [ ! -e "$DIR" ]; then
  echo "Server with the old names: run migrate_to_kaladrius.sh (decision 071)."
  exit 0
fi
mkdir -p "$DIR"
token=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "$token" | docker login -u oauth2accesstoken --password-stdin "https://$REGISTRY" >/dev/null
if ! docker pull -q "$APP_IMAGE" >/dev/null; then
  echo "Image not published to Artifact Registry yet; trying again on the next boot."
  exit 0
fi

# The rest of the deploy files (and the newest version of the scripts) come from the image.
source /dev/stdin <<<"$(docker run --rm --entrypoint cat "$APP_IMAGE" /app/deploy/server/common.sh)"
extract_deploy_files

install_schedules
"$DIR/bin/update.sh" --force

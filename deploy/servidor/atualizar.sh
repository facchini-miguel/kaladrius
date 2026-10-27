#!/bin/bash
# Pull the latest app image and restart the stack when it changed. Runs every 5 minutes
# (systemd timer). Use --forcar to restart even without a new image.
set -euo pipefail
source "$(dirname "$0")/comum.sh"

entrar_no_registro
antes=$(docker image inspect --format '{{.Id}}' "$IMAGEM_APP" 2>/dev/null || true)
docker pull -q "$IMAGEM_APP" >/dev/null
depois=$(docker image inspect --format '{{.Id}}' "$IMAGEM_APP")

if [ "$antes" != "$depois" ] || [ "${1:-}" = "--forcar" ]; then
  extrair_arquivos_de_deploy
  source "$DIR/bin/comum.sh"  # the helpers may have changed with the new image
  instalar_agendamentos
  if [ ! -f "$DIR/.env" ]; then
    echo "Sem $DIR/.env: configure o servidor antes de subir o sistema."
    exit 0
  fi
  compose up -d --remove-orphans
  docker image prune -f >/dev/null
  echo "Sistema atualizado: $(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGEM_APP")"
fi

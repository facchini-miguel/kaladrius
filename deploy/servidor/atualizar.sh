#!/bin/bash
# Pull the latest app and docs images and restart the stack when they differ from the ones
# last installed successfully. Runs every 5 minutes (systemd timer), so a failed update is
# retried on the next run. Use --forcar to restart even without a new image.
set -euo pipefail
source "$(dirname "$0")/comum.sh"

entrar_no_registro
docker pull -q "$IMAGEM_APP" >/dev/null
# The documentation site (decision 067) never blocks an update of the system.
docker pull -q "$IMAGEM_DOCS" >/dev/null 2>&1 || true
atual=$(docker image inspect --format '{{.Id}}' "$IMAGEM_APP" "$IMAGEM_DOCS" 2>/dev/null || true)
instalada=$(cat "$IMAGEM_INSTALADA" 2>/dev/null || true)

if [ "$atual" != "$instalada" ] || [ "${1:-}" = "--forcar" ]; then
  extrair_arquivos_de_deploy
  source "$DIR/bin/comum.sh"  # the helpers may have changed with the new image
  instalar_agendamentos
  if [ ! -f "$DIR/.env" ]; then
    echo "Sem $DIR/.env: configure o servidor antes de subir o sistema."
    exit 0
  fi
  compose up -d --remove-orphans
  # Recorded only after a successful start: until then every run tries again.
  echo "$atual" > "$IMAGEM_INSTALADA"
  docker image prune -f >/dev/null
  echo "Sistema atualizado: $(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGEM_APP")"
fi

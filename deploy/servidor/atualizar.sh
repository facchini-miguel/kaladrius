#!/bin/bash
# Pull the latest app and docs images and restart the stack when they differ from the ones
# last installed successfully. Runs every 5 minutes (systemd timer), so a failed update is
# retried on the next run. Use --forcar to restart even without a new image (and to try again
# an image that was refused).
#
# Automatic rollback (decision 135): after the restart the system must answer its health page
# within SAUDE_ESPERA seconds. Otherwise the app image of the last successful update (tagged
# :anterior) is put back, the new images are recorded as refused, so they are not tried again
# until a newer one is published, and the update monitor reports the failure until then.
set -euo pipefail
source "$(dirname "$0")/comum.sh"
# One run at a time: a manual --forcar waits for the timer's run instead of racing it.
exec 9>"$DIR/atualizar.lock"
flock 9
# The external monitor warns when updates fail or stop running (decision 079).
trap 'avisar_monitor MONITOR_ATUALIZACAO_URL fail' ERR

forcar=$([ "${1:-}" = "--forcar" ] && echo 1 || true)

# The new version did not come up: the previous app image goes back. The deploy files stay
# those of the new version (this script included), so the refusal is kept on the next runs.
voltar_a_anterior() {
  echo "$1" > "$IMAGEM_RECUSADA"
  echo "O sistema não respondeu com a versão nova: voltando à anterior." >&2
  if ! docker image inspect "$IMAGEM_APP_ANTERIOR" >/dev/null 2>&1; then
    echo "Não há versão anterior guardada: corrija à mão." >&2
    avisar_monitor MONITOR_ATUALIZACAO_URL fail
    exit 1
  fi
  IMAGEM_APP="$IMAGEM_APP_ANTERIOR"
  export IMAGEM_APP
  compose up -d --remove-orphans
  if sistema_no_ar; then
    echo "De volta à versão anterior; a nova fica recusada até sair outra." >&2
  else
    echo "Nem a versão anterior respondeu: corrija à mão." >&2
  fi
  avisar_monitor MONITOR_ATUALIZACAO_URL fail
  exit 1
}

entrar_no_registro
docker pull -q "$IMAGEM_APP" >/dev/null
# The documentation site (decision 067) never blocks an update of the system.
docker pull -q "$IMAGEM_DOCS" >/dev/null 2>&1 || true
atual=$(docker image inspect --format '{{.Id}}' "$IMAGEM_APP" "$IMAGEM_DOCS" 2>/dev/null || true)
instalada=$(cat "$IMAGEM_INSTALADA" 2>/dev/null || true)
recusada=$(cat "$IMAGEM_RECUSADA" 2>/dev/null || true)

# A server updated before decision 135 has no fallback yet: the image running now is the one
# installed last.
if [ "$atual" = "$instalada" ] && ! docker image inspect "$IMAGEM_APP_ANTERIOR" >/dev/null 2>&1; then
  docker tag "$IMAGEM_APP" "$IMAGEM_APP_ANTERIOR"
fi

if [ -n "$recusada" ] && [ "$atual" = "$recusada" ] && [ -z "$forcar" ]; then
  echo "A versão nova não subiu da última vez e está recusada; o sistema segue na anterior."
  avisar_monitor MONITOR_ATUALIZACAO_URL fail
  exit 0
fi

if [ "$atual" != "$instalada" ] || [ -n "$forcar" ]; then
  extrair_arquivos_de_deploy
  source "$DIR/bin/comum.sh"  # the helpers may have changed with the new image
  instalar_agendamentos
  if [ ! -f "$DIR/.env" ]; then
    echo "Sem $DIR/.env: configure o servidor antes de subir o sistema."
    exit 0
  fi
  compose up -d --remove-orphans
  sistema_no_ar || voltar_a_anterior "$atual"
  # Recorded only after the system answered: until then every run tries again.
  echo "$atual" > "$IMAGEM_INSTALADA"
  rm -f "$IMAGEM_RECUSADA"
  docker tag "$IMAGEM_APP" "$IMAGEM_APP_ANTERIOR"
  docker image prune -f >/dev/null
  echo "Sistema atualizado: $(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGEM_APP")"
fi
avisar_monitor MONITOR_ATUALIZACAO_URL

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

# The new version did not come up: the previous app image goes back, with its Compose file and
# Caddyfile, so a new Caddy or PostgreSQL digest (decision 138) is undone too. The scripts stay
# those of the new version (this one included), so the refusal is kept on the next runs.
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
  restaurar_compose_de "$IMAGEM_APP_ANTERIOR" \
    || echo "Aviso: sem o Compose da versão anterior; segue o da nova." >&2
  compose up -d --remove-orphans
  recarregar_caddy
  if sistema_no_ar; then
    echo "De volta à versão anterior; a nova fica recusada até sair outra." >&2
  else
    echo "Nem a versão anterior respondeu: corrija à mão." >&2
  fi
  avisar_monitor MONITOR_ATUALIZACAO_URL fail
  exit 1
}

entrar_no_registro
if ! instalado_por_pacote; then
  docker pull -q "$IMAGEM_APP" >/dev/null  # a failure tells the monitor (the ERR trap)
# Installed from the Linux package, an image already on the server is enough when the registry
# cannot be reached (an installation without internet, or a test image built there).
elif ! docker pull -q "$IMAGEM_APP" >/dev/null 2>&1 && ! docker image inspect "$IMAGEM_APP" >/dev/null 2>&1; then
  echo "Não foi possível baixar $IMAGEM_APP (sem internet ou o registro fora do ar)." >&2
  false  # the ERR trap tells the monitor
fi
imagens=("$IMAGEM_APP")
# The documentation site (decision 067) never blocks an update of the system, and a package
# installation has none.
if [ -n "$IMAGEM_DOCS" ]; then
  docker pull -q "$IMAGEM_DOCS" >/dev/null 2>&1 || true
  imagens+=("$IMAGEM_DOCS")
fi
atual=$(docker image inspect --format '{{.Id}}' "${imagens[@]}" 2>/dev/null || true)
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
  echo "Sistema atualizado: $(docker image inspect --format \
    '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}' "$IMAGEM_APP")"
fi
avisar_monitor MONITOR_ATUALIZACAO_URL

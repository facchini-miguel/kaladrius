# shellcheck shell=bash disable=SC2034  # the old names are read by the scripts that load this file
# Transition bridge of decision 147, for a Google Cloud server still running the scripts of 0.54
# and earlier (deploy/servidor/, Portuguese names). Those scripts load this file from the new
# image by its old path:
#   - their atualizar.sh, every 5 minutes: it copies release/servidor/*.sh to bin/ and sources
#     bin/comum.sh, then calls instalar_agendamentos, compose, sistema_no_ar…;
#   - the VM's startup script (their instalar.sh, kept in the VM's metadata), on every boot:
#     it sources this file straight from the image, then calls extrair_arquivos_de_deploy,
#     instalar_agendamentos and bin/atualizar.sh --forcar.
# Here the new helpers (deploy/server/common.sh, from the same image) are loaded and given
# their old names; instalar_agendamentos moves the server to the new names and scheduled tasks
# (migrate_legacy_names), and from then on the server runs deploy/server/. Remove this folder
# once the production VM's startup script is deploy/server/install.sh and it has updated once.
UPDATING=${ATUALIZANDO:-}
# shellcheck source=../server/common.sh
source /dev/stdin <<<"$(docker run --rm --entrypoint cat "${IMAGEM_APP:?}" /app/deploy/server/common.sh)"

IMAGEM_APP=$APP_IMAGE
IMAGEM_DOCS=$DOCS_IMAGE
IMAGEM_INSTALADA=$INSTALLED_IMAGE
IMAGEM_RECUSADA=$REFUSED_IMAGE
IMAGEM_APP_ANTERIOR=$PREVIOUS_APP_IMAGE
export IMAGEM_APP IMAGEM_DOCS

# The old atualizar.sh changes IMAGEM_APP to go back to the previous version.
compose() {
  APP_IMAGE=$IMAGEM_APP
  DOCS_IMAGE=$IMAGEM_DOCS
  IMAGEM_APP=$APP_IMAGE IMAGEM_DOCS=$DOCS_IMAGE docker compose -f "$COMPOSE_PATH" "$@"
}
valor_do_env() { env_value "$@"; }
instalado_por_pacote() { installed_by_package; }
avisar_monitor() { notify_monitor "$@"; }
entrar_no_registro() { registry_login; }
sistema_no_ar() { system_up; }
restaurar_compose_de() { restore_compose_from "$@"; }
guardar_compose_anterior() { save_previous_compose; }
recarregar_caddy() { reload_caddy; }
extrair_arquivos_de_deploy() {
  APP_IMAGE=$IMAGEM_APP
  extract_deploy_files
}
instalar_agendamentos() {
  APP_IMAGE=$IMAGEM_APP
  install_schedules
}

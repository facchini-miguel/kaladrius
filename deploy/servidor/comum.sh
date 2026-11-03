# Shared settings and helpers for the server scripts (sourced, not executed).
DIR=/opt/kaladrius
REGISTRO=us-east1-docker.pkg.dev
IMAGEM_APP="$REGISTRO/medical-system-facchini/kaladrius/app:latest"
IMAGEM_DOCS="$REGISTRO/medical-system-facchini/kaladrius/docs:latest"
BUCKET_BACKUP=kaladrius-backups
# Id of the image running since the last successful update (written by atualizar.sh).
IMAGEM_INSTALADA="$DIR/imagem-instalada"

# Value of one variable of the server .env (empty when missing). The scripts never source
# the whole file: it holds the app's passwords.
valor_do_env() {
  grep -m1 "^$1=" "$DIR/.env" 2>/dev/null | cut -d= -f2- || true
}

# Installed from the Linux package (.deb or .rpm, decision 140): the package ships the deploy
# files and the scripts, and runs the public image of its own version (ghcr.io), pinned by
# digest in release/pacote-linux when the package is built (a file; Google Cloud's release/ also
# gets the deploy/pacote folder, with the package's sources); updates come with apt or dnf, and
# backups go to a local folder. KALADRIUS_IMAGEM (environment or .env) names another image,
# for tests or an installation without internet.
PACOTE="$DIR/release/pacote-linux"
instalado_por_pacote() {
  [ -f "$PACOTE" ]
}
if instalado_por_pacote; then
  VERSAO_DO_PACOTE=$(sed -n 's/^VERSAO=//p' "$PACOTE")
  REGISTRO=ghcr.io
  IMAGEM_APP=${KALADRIUS_IMAGEM:-$(valor_do_env KALADRIUS_IMAGEM)}
  IMAGEM_APP=${IMAGEM_APP:-$(sed -n 's/^IMAGEM=//p' "$PACOTE")}
  IMAGEM_DOCS=""  # the documentation site is not part of a clinic's installation
fi

# The repository of an image reference, without its tag and digest
# (ghcr.io/a/b:1.0@sha256:… → ghcr.io/a/b; a registry's port is kept).
repositorio_de() {
  local ref=${1%@*}
  case "${ref##*/}" in *:*) ref=${ref%:*} ;; esac
  echo "$ref"
}

# Automatic rollback (decision 135): the app image of the last successful update, kept under
# this tag to go back to, and the ids of an update that did not come up (not tried again).
IMAGEM_APP_ANTERIOR="$(repositorio_de "$IMAGEM_APP"):anterior"
IMAGEM_RECUSADA="$DIR/imagem-recusada"
# Installed from the package, the Compose file and the Caddyfile of that version too: the package
# replaces those of release/ with the next version's before it is started.
ANTERIOR="$DIR/anterior"
# The Compose file of the running version (release/, or anterior/ after a rollback).
COMPOSE_ARQUIVO="$DIR/release/docker-compose.prod.yml"
# How long a new version has to answer after starting (it migrates the database first).
SAUDE_ESPERA=${SAUDE_ESPERA:-300}
export IMAGEM_APP IMAGEM_DOCS
# The local backup folder of a package installation (decision 140), unless .env names another.
BACKUP_PASTA_PADRAO=/var/backups/kaladrius

# A server installed before 0.26.1 keeps everything in /opt/medical-system. Until
# migrar_para_kaladrius.sh moves it, the new scripts do nothing: starting the "kaladrius"
# Compose project there would bring up an empty database next to the real one.
if [ -d /opt/medical-system ] && [ ! -e "$DIR" ] && [ -z "${MIGRANDO:-}" ]; then
  echo "Servidor com os nomes antigos: rode migrar_para_kaladrius.sh (decisão 071)." >&2
  exit 1
fi

# Signal to an external monitor such as Healthchecks.io (decision 078). $1 names the .env
# variable with the check's address (MONITOR_SISTEMA_URL, MONITOR_BACKUP_URL); $2 "fail"
# reports a failure. Does nothing when the variable is not set, and never fails the caller.
avisar_monitor() {
  local url
  url=$(valor_do_env "$1")
  [ -n "$url" ] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "$url${2:+/$2}" || echo "Aviso: o monitor $1 não respondeu." >&2
}

# An installation for the clinic's internal network (KALADRIUS_ACESSO=rede-interna): Caddy
# serves it with its own local certificate authority, which this server's curl does not know.
rede_interna() {
  [ "$(valor_do_env KALADRIUS_ACESSO)" = rede-interna ]
}

# curl's options (in OPCOES_CURL) to reach this installation's site $1 from the server itself.
# On the internal network, Caddy's local certificate authority, which this server's curl does not
# know. Installed from the package with a domain, through this server's own Caddy (127.0.0.1): a
# clinic's router often does not send back inside what the server sends to the clinic's public
# address (no "hairpin NAT"), and a new version must not be refused for that. On Google Cloud,
# through the internet, like anyone.
opcoes_para_o_site() {
  OPCOES_CURL=()
  if rede_interna; then
    OPCOES_CURL=(--insecure)
  elif instalado_por_pacote; then
    OPCOES_CURL=(--resolve "$1:443:127.0.0.1")
  fi
}

pasta_dos_backups() {
  local pasta
  pasta=$(valor_do_env KALADRIUS_BACKUP_PASTA)
  echo "${pasta:-$BACKUP_PASTA_PADRAO}"
}

# The system answers its health page, with the database, at its first address and through
# Caddy within SAUDE_ESPERA seconds.
sistema_no_ar() {
  local site fim
  site=$(valor_do_env SITE_HOSTNAME | cut -d, -f1 | tr -d ' ')
  opcoes_para_o_site "$site"
  fim=$(($(date +%s) + SAUDE_ESPERA))
  until curl -fsS -m 10 "${OPCOES_CURL[@]}" -o /dev/null "https://$site/api/v1/saude" 2>/dev/null; do
    [ "$(date +%s)" -lt "$fim" ] || return 1
    sleep 5
  done
}

# Access token of the VM's service account (no keys stored on the server).
token_google() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4
}

entrar_no_registro() {
  instalado_por_pacote && return 0  # ghcr.io: public image, no login
  token_google | docker login -u oauth2accesstoken --password-stdin "https://$REGISTRO" >/dev/null
}

compose() {
  docker compose -f "$COMPOSE_ARQUIVO" "$@"
}

# The PostgreSQL image of the running Compose file, digest included (decision 138), for the
# throwaway containers of the restore test: the same database production writes its backups with.
imagem_postgres() {
  local imagem
  imagem=$(sed -n 's/^ *image: *\(postgres:[^ ]*\).*/\1/p' "$COMPOSE_ARQUIVO")
  [ -n "$imagem" ] || { echo "Sem imagem do PostgreSQL em docker-compose.prod.yml." >&2; return 1; }
  echo "$imagem"
}

# The Compose file and the Caddyfile of an app image (the rollback's, decision 135): they name
# the Caddy and PostgreSQL digests (decision 138), so going back to the previous app image also
# puts back its Caddy and PostgreSQL. The scripts stay those of the new version. Installed from
# the package, the copy kept by guardar_compose_anterior: release/ belongs to the package.
restaurar_compose_de() {
  if instalado_por_pacote; then
    [ -f "$ANTERIOR/docker-compose.prod.yml" ] || return 1
    COMPOSE_ARQUIVO="$ANTERIOR/docker-compose.prod.yml"
    return 0
  fi
  docker run --rm --entrypoint sh "$1" -c 'tar -C /app/deploy -cf - docker-compose.prod.yml Caddyfile' \
    | tar -C "$DIR/release" -xf -
}

# Installed from the package, the version that just came up keeps its Compose file and Caddyfile
# in $ANTERIOR, beside its app image under :anterior, for the next update's rollback. Replaced
# whole (mv): a rollback never finds half of it. On Google Cloud they are inside the app image.
guardar_compose_anterior() {
  instalado_por_pacote || return 0
  rm -rf "$ANTERIOR.novo"
  mkdir -p "$ANTERIOR.novo"
  cp "$DIR/release/docker-compose.prod.yml" "$DIR/release/Caddyfile" "$ANTERIOR.novo/"
  ln -sfn ../.env "$ANTERIOR.novo/.env"  # Compose reads the ${VAR} values from .env beside it
  rm -rf "$ANTERIOR"
  mv "$ANTERIOR.novo" "$ANTERIOR"
}

# Installed from the package, after an automatic rollback: the package's version is refused and
# the previous one runs (its app image, Compose file and Caddyfile). Every command then acts on
# the previous one, so restarting the system never brings back the version that did not come up;
# installing the package again tries it again (atualizar.sh --forcar).
na_versao_anterior() {
  local recusada id
  instalado_por_pacote || return 1
  recusada=$(cat "$IMAGEM_RECUSADA" 2>/dev/null) || return 1
  id=$(docker image inspect --format '{{.Id}}' "$IMAGEM_APP" 2>/dev/null) || return 1
  [ "$id" = "$recusada" ] || return 1
  docker image inspect "$IMAGEM_APP_ANTERIOR" >/dev/null 2>&1
}

usar_a_versao_anterior() {
  IMAGEM_APP="$IMAGEM_APP_ANTERIOR"
  export IMAGEM_APP
  restaurar_compose_de "$IMAGEM_APP" || true  # without the copy, the package's own files
}

# Decided here, once, for every script that sources this file (the `kaladrius` command, backups,
# health, the restore test, the removal): after a rollback they all act on the version running.
# Only atualizar.sh (ATUALIZANDO) decides the version itself. NA_ANTERIOR tells the commands.
NA_ANTERIOR=""
if [ -z "${ATUALIZANDO:-}" ] && na_versao_anterior; then
  NA_ANTERIOR=1
  usar_a_versao_anterior
fi

# Copy the deploy files shipped inside the app image to $DIR/release and $DIR/bin.
extrair_arquivos_de_deploy() {
  local tmp
  if instalado_por_pacote; then  # the package brought them
    ln -sfn ../.env "$DIR/release/.env"
    return 0
  fi
  tmp=$(mktemp -d)
  docker run --rm --entrypoint sh "$IMAGEM_APP" -c 'tar -C /app/deploy -cf - .' | tar -C "$tmp" -xf -
  mkdir -p "$DIR/release" "$DIR/bin"
  cp -r "$tmp"/. "$DIR/release/"
  # Compose reads the ${VAR} values of docker-compose.prod.yml from .env beside it.
  ln -sfn ../.env "$DIR/release/.env"
  instalar_scripts
  rm -r "$tmp"
}

# Copy every server script from the release to $DIR/bin. Replaced atomically (mv), so a
# running script is never overwritten in place.
instalar_scripts() {
  local script
  for script in "$DIR"/release/servidor/*.sh; do
    cp "$script" "$DIR/bin/$(basename "$script").novo"
    chmod 755 "$DIR/bin/$(basename "$script").novo"
    mv -f "$DIR/bin/$(basename "$script").novo" "$DIR/bin/$(basename "$script")"
  done
}

# Install (or update) the systemd units shipped with the deploy files.
instalar_agendamentos() {
  if instalado_por_pacote; then  # its units came with the package; updates come with apt/dnf
    mkdir -p "$DIR/saude"
    systemctl daemon-reload
    systemctl enable --now kaladrius-backup.timer kaladrius-saude.timer kaladrius-restauracao.timer
    recarregar_caddy
    return 0
  fi
  # Also here: a server updating from an older version copied only the scripts it knew.
  instalar_scripts
  # Health samples, read by the app through a read-only mount (docker-compose.prod.yml).
  mkdir -p "$DIR/saude"
  cp "$DIR"/release/servidor/*.service "$DIR"/release/servidor/*.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now kaladrius-atualizar.timer kaladrius-backup.timer \
    kaladrius-saude.timer kaladrius-restauracao.timer kaladrius-demonstracao.timer
  # Also here, not only in atualizar.sh: an update is run by the previous version of
  # atualizar.sh, which only calls the helpers of the new version.
  recarregar_caddy
}

# `compose up` does not restart Caddy when only the content of the Caddyfile changed, so
# apply it (a no-op when unchanged). Caddy keeps the old configuration if the new one fails.
recarregar_caddy() {
  # grep without -q: it reads all its input, so the writer never dies of a closed pipe (SIGPIPE),
  # which pipefail would take as a failure.
  if compose ps --status running --services 2>/dev/null | grep -x caddy >/dev/null; then
    compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile </dev/null >/dev/null 2>&1 \
      || echo "Aviso: o Caddy não aceitou o novo Caddyfile e continua com o anterior."
  fi
}

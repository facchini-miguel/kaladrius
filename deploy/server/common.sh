# shellcheck shell=bash
# Shared settings and helpers for the server scripts (sourced, not executed).
DIR=/opt/kaladrius
REGISTRY=us-east1-docker.pkg.dev
APP_IMAGE="$REGISTRY/medical-system-facchini/kaladrius/app:latest"
DOCS_IMAGE="$REGISTRY/medical-system-facchini/kaladrius/docs:latest"
BACKUP_BUCKET=kaladrius-backups
# Id of the image running since the last successful update (written by update.sh).
INSTALLED_IMAGE="$DIR/installed-image"
# The systemd units' folder (another one in the tests).
SYSTEMD_DIR=${SYSTEMD_DIR:-/etc/systemd/system}

# The .env variables renamed by decision 147, as "current=before". A .env written before is
# migrated by migrate_legacy_names; env_value also reads the old name, for a line added by hand
# from older documentation, and takes an old name too (the scripts of 0.54 and earlier).
LEGACY_ENV_NAMES="KALADRIUS_ACCESS=KALADRIUS_ACESSO KALADRIUS_BACKUP_DIR=KALADRIUS_BACKUP_PASTA
KALADRIUS_BACKUP_DAYS=KALADRIUS_BACKUP_DIAS KALADRIUS_IMAGE=KALADRIUS_IMAGEM
MONITOR_SYSTEM_URL=MONITOR_SISTEMA_URL MONITOR_UPDATE_URL=MONITOR_ATUALIZACAO_URL
MONITOR_RESTORE_URL=MONITOR_RESTAURACAO_URL MONITOR_CERTIFICATE_URL=MONITOR_CERTIFICADO_URL
MONITOR_RESOURCES_URL=MONITOR_RECURSOS_URL MONITOR_DEMO_URL=MONITOR_DEMONSTRACAO_URL
APP_IMAGE=IMAGEM_APP DOCS_IMAGE=IMAGEM_DOCS"
# The app's variables renamed by decision 149. migrate_env adds the new name and keeps the old
# one: after a rollback, the previous version's app reads only the old name (without
# DJANGO_PROXY_REVERSO, behind Caddy, nobody could log in).
LEGACY_APP_ENV_NAMES="DJANGO_REVERSE_PROXY=DJANGO_PROXY_REVERSO DJANGO_DEMO=DJANGO_DEMONSTRACAO
DJANGO_HEALTH_MONITORED=DJANGO_SAUDE_MONITORADA DJANGO_BACKUP_MONITORED=DJANGO_BACKUP_MONITORADO"

# Value of one variable of the server .env (empty when missing). The scripts never source
# the whole file: it holds the app's passwords.
env_value() {
  local name=$1 pair value=""
  for pair in $LEGACY_ENV_NAMES $LEGACY_APP_ENV_NAMES; do
    if [ "${pair#*=}" = "$name" ]; then name=${pair%%=*}; fi
  done
  value=$(grep -m1 "^$name=" "$DIR/.env" 2>/dev/null | cut -d= -f2-) || true
  if [ -z "$value" ]; then
    for pair in $LEGACY_ENV_NAMES $LEGACY_APP_ENV_NAMES; do
      if [ "${pair%%=*}" = "$name" ]; then
        value=$(grep -m1 "^${pair#*=}=" "$DIR/.env" 2>/dev/null | cut -d= -f2-) || true
      fi
    done
  fi
  echo "$value"
}

# Variables a person may set when running a script (the old names still work, decision 147).
KALADRIUS_IMAGE=${KALADRIUS_IMAGE:-${KALADRIUS_IMAGEM:-}}
HEALTH_WAIT=${HEALTH_WAIT:-${SAUDE_ESPERA:-300}}

# Installed from the Linux package (.deb, .rpm or Arch Linux, decision 140): the package ships
# the deploy files and the scripts, and runs the public image of its own version (ghcr.io),
# pinned by digest in release/linux-package when the package is built (a file; Google Cloud's
# release/ also gets the deploy/package folder, with the package's sources); an update is the
# next version's package installed over it, and backups go to a local folder. KALADRIUS_IMAGE
# (environment or .env) names another image, for tests or an installation without internet.
PACKAGE_MARKER="$DIR/release/linux-package"
installed_by_package() {
  [ -f "$PACKAGE_MARKER" ]
}
if installed_by_package; then
  PACKAGE_VERSION=$(sed -n 's/^VERSION=//p' "$PACKAGE_MARKER")
  REGISTRY=ghcr.io
  APP_IMAGE=${KALADRIUS_IMAGE:-$(env_value KALADRIUS_IMAGE)}
  APP_IMAGE=${APP_IMAGE:-$(sed -n 's/^IMAGE=//p' "$PACKAGE_MARKER")}
  DOCS_IMAGE=""  # the documentation site is not part of a clinic's installation
fi

# The repository of an image reference, without its tag and digest
# (ghcr.io/a/b:1.0@sha256:… → ghcr.io/a/b; a registry's port is kept).
repository_of() {
  local ref=${1%@*}
  case "${ref##*/}" in *:*) ref=${ref%:*} ;; esac
  echo "$ref"
}

# Automatic rollback (decision 135): the app image of the last successful update, kept under
# this tag to go back to, and the ids of an update that did not come up (not tried again).
PREVIOUS_APP_IMAGE="$(repository_of "$APP_IMAGE"):previous"
REFUSED_IMAGE="$DIR/refused-image"
# Installed from the package, the Compose file and the Caddyfile of that version too: the package
# replaces those of release/ with the next version's before it is started.
PREVIOUS_DIR="$DIR/previous"
# The Compose file of the running version (release/, or previous/ after a rollback).
COMPOSE_PATH="$DIR/release/docker-compose.prod.yml"
# The local backup folder of a package installation (decision 140), unless .env names another.
DEFAULT_BACKUP_DIR=/var/backups/kaladrius
# Old Compose files (a rollback to a version before decision 147) name the images IMAGEM_APP
# and IMAGEM_DOCS: compose() hands them both names.
export APP_IMAGE DOCS_IMAGE

# A server installed before 0.26.1 keeps everything in /opt/medical-system. Until
# migrate_to_kaladrius.sh moves it, the new scripts do nothing: starting the "kaladrius"
# Compose project there would bring up an empty database next to the real one.
if [ -d /opt/medical-system ] && [ ! -e "$DIR" ] && [ -z "${MIGRATING:-}" ]; then
  echo "Server with the old names: run migrate_to_kaladrius.sh (decision 071)." >&2
  exit 1
fi

# Signal to an external monitor such as Healthchecks.io (decision 078). $1 names the .env
# variable with the check's address (MONITOR_SYSTEM_URL, MONITOR_BACKUP_URL); $2 "fail"
# reports a failure. Does nothing when the variable is not set, and never fails the caller.
notify_monitor() {
  local url
  url=$(env_value "$1")
  [ -n "$url" ] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "$url${2:+/$2}" || echo "Warning: monitor $1 did not answer." >&2
}

# An installation for the clinic's internal network (KALADRIUS_ACCESS=internal-network; before
# decision 147, rede-interna): Caddy serves it with its own local certificate authority, which
# this server's curl does not know.
internal_network() {
  case "$(env_value KALADRIUS_ACCESS)" in
    internal-network | rede-interna) return 0 ;;
    *) return 1 ;;
  esac
}

# curl's options (in CURL_OPTIONS) to reach this installation's site $1 from the server itself.
# On the internal network, Caddy's local certificate authority, which this server's curl does not
# know. Installed from the package with a domain, through this server's own Caddy (127.0.0.1): a
# clinic's router often does not send back inside what the server sends to the clinic's public
# address (no "hairpin NAT"), and a new version must not be refused for that. On Google Cloud,
# through the internet, like anyone.
site_curl_options() {
  CURL_OPTIONS=()
  if internal_network; then
    CURL_OPTIONS=(--insecure)
  elif installed_by_package; then
    CURL_OPTIONS=(--resolve "$1:443:127.0.0.1")
  fi
}

backup_dir() {
  local dir
  dir=$(env_value KALADRIUS_BACKUP_DIR)
  echo "${dir:-$DEFAULT_BACKUP_DIR}"
}

# The system answers its health page, with the database, at its first address and through
# Caddy within HEALTH_WAIT seconds.
system_up() {
  local site end
  site=$(env_value SITE_HOSTNAME | cut -d, -f1 | tr -d ' ')
  site_curl_options "$site"
  end=$(($(date +%s) + HEALTH_WAIT))
  until curl -fsS -m 10 "${CURL_OPTIONS[@]}" -o /dev/null "https://$site/api/v1/saude" 2>/dev/null; do
    [ "$(date +%s)" -lt "$end" ] || return 1
    sleep 5
  done
}

# Access token of the VM's service account (no keys stored on the server).
google_token() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4
}

registry_login() {
  installed_by_package && return 0  # ghcr.io: public image, no login
  google_token | docker login -u oauth2accesstoken --password-stdin "https://$REGISTRY" >/dev/null
}

compose() {
  IMAGEM_APP=$APP_IMAGE IMAGEM_DOCS=$DOCS_IMAGE docker compose -f "$COMPOSE_PATH" "$@"
}

# A management command of the running app: `manage NEW_ARGS… [-- OLD_ARGS…]`. The names and
# options are those of decision 148; after a rollback the app may be a version from before it,
# which only knows the ones given after --.
manage() {
  local -a new=() old=()
  while [ $# -gt 0 ] && [ "$1" != -- ]; do
    new+=("$1")
    shift
  done
  if [ $# -gt 0 ]; then
    shift
    old=("$@")
  fi
  if [ "${#old[@]}" -gt 0 ] && ! compose exec -T app python manage.py help "${new[0]}" >/dev/null 2>&1 </dev/null; then
    compose exec -T app python manage.py "${old[@]}"
  else
    compose exec -T app python manage.py "${new[@]}"
  fi
}

# The PostgreSQL image of the running Compose file, digest included (decision 138), for the
# throwaway containers of the restore test: the same database production writes its backups with.
postgres_image() {
  local image
  image=$(sed -n 's/^ *image: *\(postgres:[^ ]*\).*/\1/p' "$COMPOSE_PATH")
  [ -n "$image" ] || { echo "No PostgreSQL image in docker-compose.prod.yml." >&2; return 1; }
  echo "$image"
}

# The Compose file and the Caddyfile of an app image (the rollback's, decision 135): they name
# the Caddy and PostgreSQL digests (decision 138), so going back to the previous app image also
# puts back its Caddy and PostgreSQL. The scripts stay those of the new version. Installed from
# the package, the copy kept by save_previous_compose: release/ belongs to the package.
restore_compose_from() {
  if installed_by_package; then
    [ -f "$PREVIOUS_DIR/docker-compose.prod.yml" ] || return 1
    COMPOSE_PATH="$PREVIOUS_DIR/docker-compose.prod.yml"
    return 0
  fi
  docker run --rm --entrypoint sh "$1" -c 'tar -C /app/deploy -cf - docker-compose.prod.yml Caddyfile' \
    | tar -C "$DIR/release" -xf -
}

# Installed from the package, the version that just came up keeps its Compose file and Caddyfile
# in $PREVIOUS_DIR, beside its app image under :previous, for the next update's rollback. Replaced
# whole (mv): a rollback never finds half of it. On Google Cloud they are inside the app image.
save_previous_compose() {
  installed_by_package || return 0
  rm -rf "$PREVIOUS_DIR.new"
  mkdir -p "$PREVIOUS_DIR.new"
  cp "$DIR/release/docker-compose.prod.yml" "$DIR/release/Caddyfile" "$PREVIOUS_DIR.new/"
  ln -sfn ../.env "$PREVIOUS_DIR.new/.env"  # Compose reads the ${VAR} values from .env beside it
  rm -rf "$PREVIOUS_DIR"
  mv "$PREVIOUS_DIR.new" "$PREVIOUS_DIR"
}

# Installed from the package, after an automatic rollback: the package's version is refused and
# the previous one runs (its app image, Compose file and Caddyfile). Every command then acts on
# the previous one, so restarting the system never brings back the version that did not come up;
# installing the package again tries it again (update.sh --force).
on_previous_version() {
  local refused id
  installed_by_package || return 1
  refused=$(cat "$REFUSED_IMAGE" 2>/dev/null) || return 1
  id=$(docker image inspect --format '{{.Id}}' "$APP_IMAGE" 2>/dev/null) || return 1
  [ "$id" = "$refused" ] || return 1
  docker image inspect "$PREVIOUS_APP_IMAGE" >/dev/null 2>&1
}

use_previous_version() {
  APP_IMAGE="$PREVIOUS_APP_IMAGE"
  restore_compose_from "$APP_IMAGE" || true  # without the copy, the package's own files
}

# Decided here, once, for every script that sources this file (the `kaladrius` command, backups,
# health, the restore test, the removal): after a rollback they all act on the version running.
# Only update.sh (UPDATING) decides the version itself. ON_PREVIOUS tells the commands.
ON_PREVIOUS=""
if [ -z "${UPDATING:-}" ] && on_previous_version; then
  ON_PREVIOUS=1
  use_previous_version
fi

# Copy the deploy files shipped inside the app image to $DIR/release and $DIR/bin.
extract_deploy_files() {
  local tmp
  if installed_by_package; then  # the package brought them
    ln -sfn ../.env "$DIR/release/.env"
    return 0
  fi
  tmp=$(mktemp -d)
  docker run --rm --entrypoint sh "$APP_IMAGE" -c 'tar -C /app/deploy -cf - .' | tar -C "$tmp" -xf -
  mkdir -p "$DIR/release" "$DIR/bin"
  cp -r "$tmp"/. "$DIR/release/"
  # Compose reads the ${VAR} values of docker-compose.prod.yml from .env beside it.
  ln -sfn ../.env "$DIR/release/.env"
  install_scripts
  rm -r "$tmp"
}

# Copy every server script from the release to $DIR/bin. Replaced atomically (mv), so a
# running script is never overwritten in place.
install_scripts() {
  local script
  for script in "$DIR"/release/server/*.sh; do
    cp "$script" "$DIR/bin/$(basename "$script").new"
    chmod 755 "$DIR/bin/$(basename "$script").new"
    mv -f "$DIR/bin/$(basename "$script").new" "$DIR/bin/$(basename "$script")"
  done
  # The VM's startup script of a server created before decision 147 runs bin/atualizar.sh
  # --forcar on every boot: kept as a pointer to update.sh until the startup script is
  # install.sh (docs/docs/project/production.md).
  printf '%s\n' '#!/bin/bash' \
    '# Before decision 147 this was the update script; the VM'"'"'s old startup script still runs it.' \
    'exec "$(dirname "$0")/update.sh" ${1:+--force}' >"$DIR/bin/atualizar.sh.new"
  chmod 755 "$DIR/bin/atualizar.sh.new"
  mv -f "$DIR/bin/atualizar.sh.new" "$DIR/bin/atualizar.sh"
}

# Install (or update) the systemd units shipped with the deploy files.
install_schedules() {
  migrate_legacy_names
  if installed_by_package; then  # its units came with the package, and so do its updates
    mkdir -p "$DIR/health"
    systemctl daemon-reload
    systemctl enable --now kaladrius-backup.timer kaladrius-health.timer kaladrius-restore-test.timer
    reload_caddy
    return 0
  fi
  # Also here: a server updating from an older version copied only the scripts it knew.
  install_scripts
  # Health samples, read by the app through a read-only mount (docker-compose.prod.yml).
  mkdir -p "$DIR/health"
  cp "$DIR"/release/server/*.service "$DIR"/release/server/*.timer "$SYSTEMD_DIR/"
  systemctl daemon-reload
  systemctl enable --now kaladrius-update.timer kaladrius-backup.timer \
    kaladrius-health.timer kaladrius-restore-test.timer kaladrius-demo-reset.timer
  # Also here, not only in update.sh: an update is run by the previous version of update.sh,
  # which only calls the helpers of the new version.
  reload_caddy
}

# Names a server installed before decision 147 still has, changed to the current ones; safe to
# run again (each step only when the old name is there and the new one is not). Run as root by
# install_schedules (every update) and by the package's post_install.sh, before anything reads
# them. Only the names change: the data, the backups and the database stay where they are.
migrate_legacy_names() {
  local unit file pair old new image
  # The units moved aside by decision 071's migration, beside the ones moved here.
  if [ -d "$DIR/unidades-antigas" ] && [ ! -e "$DIR/legacy/units" ]; then
    mkdir -p "$DIR/legacy"
    mv "$DIR/unidades-antigas" "$DIR/legacy/units"
  fi
  # The scheduled tasks under their old names: stopped and disabled (a task already running
  # finishes), and on Google Cloud their unit files are moved to $DIR/legacy/units (the package
  # manager removes the package's own; their links in *.wants stay behind, so they go here).
  for unit in kaladrius-atualizar kaladrius-saude kaladrius-restauracao kaladrius-demonstracao; do
    if [ -e "$SYSTEMD_DIR/$unit.timer" ] || compgen -G "$SYSTEMD_DIR/*.wants/$unit.timer" >/dev/null; then
      systemctl stop "$unit.timer" >/dev/null 2>&1 || true
      systemctl disable "$unit.timer" >/dev/null 2>&1 || true
      rm -f "$SYSTEMD_DIR"/*.wants/"$unit.timer"
    fi
    for file in "$SYSTEMD_DIR/$unit.service" "$SYSTEMD_DIR/$unit.timer"; do
      if [ -f "$file" ]; then
        mkdir -p "$DIR/legacy/units"
        mv -f "$file" "$DIR/legacy/units/"
      fi
    done
  done
  for pair in imagem-instalada:installed-image imagem-recusada:refused-image anterior:previous \
    admin-criado:admin-created sem-repositorio:no-repository demonstracao:demo \
    demo/base-data:demo/base-date saude:health health/amostras.jsonl:health/samples.jsonl; do
    old="$DIR/${pair%%:*}" new="$DIR/${pair#*:}"
    if [ -e "$old" ] && [ ! -e "$new" ]; then mv "$old" "$new"; fi
  done
  # The previous version's image, kept for the rollback under the tag :anterior: tagged again,
  # and the old tag removed (the image stays, under :previous).
  image="$(repository_of "$APP_IMAGE"):anterior"
  if docker image inspect "$image" >/dev/null 2>&1 \
    && ! docker image inspect "$PREVIOUS_APP_IMAGE" >/dev/null 2>&1; then
    docker tag "$image" "$PREVIOUS_APP_IMAGE" && docker image rm "$image" >/dev/null 2>&1 || true
  fi
  migrate_env
  # The package repository's files of 0.54 (package files: an .rpm update removes them only
  # after this runs, so the folder left empty goes on the next update).
  rmdir "$DIR/repositorio" 2>/dev/null || true
  # Google Cloud: the scripts under their old names, moved to $DIR/legacy/bin (bin/atualizar.sh
  # is install_scripts' pointer). The package manager removes the package's own.
  if ! installed_by_package; then
    for old in comum.sh saude.sh testar_restauracao.sh reiniciar_demonstracao.sh instalar.sh \
      migrar_para_kaladrius.sh; do
      if [ -f "$DIR/bin/$old" ]; then
        mkdir -p "$DIR/legacy/bin"
        mv -f "$DIR/bin/$old" "$DIR/legacy/bin/"
      fi
    done
  fi
}

# .env with the variable names of decision 147 (LEGACY_ENV_NAMES) and the access value
# internal-network, plus the app's names of decision 149 (LEGACY_APP_ENV_NAMES) beside the old
# ones; the file as it was is kept once, beside it, as .env.before-147.
migrate_env() {
  local pair script="" new
  [ -f "$DIR/.env" ] || return 0
  for pair in $LEGACY_ENV_NAMES; do
    script="${script}s/^${pair#*=}=/${pair%%=*}=/;"
  done
  script="${script}s/^KALADRIUS_ACCESS=rede-interna\$/KALADRIUS_ACCESS=internal-network/"
  new=$(mktemp "$DIR/.env.XXXXXX")
  sed "$script" "$DIR/.env" >"$new"
  for pair in $LEGACY_APP_ENV_NAMES; do
    if grep -q "^${pair#*=}=" "$new" && ! grep -q "^${pair%%=*}=" "$new"; then
      echo "${pair%%=*}=$(grep -m1 "^${pair#*=}=" "$new" | cut -d= -f2-)" >>"$new"
    fi
  done
  if cmp -s "$new" "$DIR/.env"; then
    rm -f "$new"
    return 0
  fi
  if [ ! -e "$DIR/.env.before-147" ]; then
    cp -p "$DIR/.env" "$DIR/.env.before-147"
    chmod 600 "$DIR/.env.before-147"
  fi
  chmod 600 "$new"
  mv -f "$new" "$DIR/.env"
}

# The Compose service $1 (app, db, caddy) is running. grep without -q: it reads all its input,
# so the writer never dies of a closed pipe (SIGPIPE), which pipefail would take as a failure.
service_running() {
  compose ps --status running --services 2>/dev/null | grep -x "$1" >/dev/null
}

# `compose up` does not restart Caddy when only the content of the Caddyfile changed, so
# apply it (a no-op when unchanged). Caddy keeps the old configuration if the new one fails.
reload_caddy() {
  if service_running caddy; then
    compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile </dev/null >/dev/null 2>&1 \
      || echo "Warning: Caddy did not accept the new Caddyfile and keeps the previous one."
  fi
}

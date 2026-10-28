# Shared settings and helpers for the server scripts (sourced, not executed).
DIR=/opt/kaladrius
REGISTRO=us-east1-docker.pkg.dev
IMAGEM_APP="$REGISTRO/medical-system-facchini/kaladrius/app:latest"
IMAGEM_DOCS="$REGISTRO/medical-system-facchini/kaladrius/docs:latest"
BUCKET_BACKUP=kaladrius-backups
# Id of the image running since the last successful update (written by atualizar.sh).
IMAGEM_INSTALADA="$DIR/imagem-instalada"
export IMAGEM_APP IMAGEM_DOCS

# A server installed before 0.26.1 keeps everything in /opt/medical-system. Until
# migrar_para_kaladrius.sh moves it, the new scripts do nothing: starting the "kaladrius"
# Compose project there would bring up an empty database next to the real one.
if [ -d /opt/medical-system ] && [ ! -e "$DIR" ] && [ -z "${MIGRANDO:-}" ]; then
  echo "Servidor com os nomes antigos: rode migrar_para_kaladrius.sh (decisão 071)." >&2
  exit 1
fi

# Access token of the VM's service account (no keys stored on the server).
token_google() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4
}

entrar_no_registro() {
  token_google | docker login -u oauth2accesstoken --password-stdin "https://$REGISTRO" >/dev/null
}

compose() {
  docker compose -f "$DIR/release/docker-compose.prod.yml" "$@"
}

# Copy the deploy files shipped inside the app image to $DIR/release and $DIR/bin.
extrair_arquivos_de_deploy() {
  local tmp
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
  # Also here: a server updating from an older version copied only the scripts it knew.
  instalar_scripts
  # Health samples, read by the app through a read-only mount (docker-compose.prod.yml).
  mkdir -p "$DIR/saude"
  cp "$DIR"/release/servidor/*.service "$DIR"/release/servidor/*.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now kaladrius-atualizar.timer kaladrius-backup.timer \
    kaladrius-saude.timer
  # Also here, not only in atualizar.sh: an update is run by the previous version of
  # atualizar.sh, which only calls the helpers of the new version.
  recarregar_caddy
}

# `compose up` does not restart Caddy when only the content of the Caddyfile changed, so
# apply it (a no-op when unchanged). Caddy keeps the old configuration if the new one fails.
recarregar_caddy() {
  if compose ps --status running --services 2>/dev/null | grep -qx caddy; then
    compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile \
      || echo "Aviso: o Caddy não aceitou o novo Caddyfile e continua com o anterior."
  fi
}

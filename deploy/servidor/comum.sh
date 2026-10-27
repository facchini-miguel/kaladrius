# Shared settings and helpers for the server scripts (sourced, not executed).
DIR=/opt/medical-system
REGISTRO=us-east1-docker.pkg.dev
IMAGEM_APP="$REGISTRO/medical-system-facchini/medical-system/app:latest"
BUCKET_BACKUP=medical-system-facchini-backups
# Id of the image running since the last successful update (written by atualizar.sh).
IMAGEM_INSTALADA="$DIR/imagem-instalada"
export IMAGEM_APP

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
  systemctl enable --now medical-system-atualizar.timer medical-system-backup.timer \
    medical-system-saude.timer
}

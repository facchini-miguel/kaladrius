# Shared settings and helpers for the server scripts (sourced, not executed).
DIR=/opt/medical-system
REGISTRO=us-east1-docker.pkg.dev
IMAGEM_APP="$REGISTRO/medical-system-facchini/medical-system/app:latest"
BUCKET_BACKUP=medical-system-facchini-backups
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
  # Replace the scripts atomically (mv), so a running script is never overwritten in place.
  for script in comum.sh atualizar.sh backup.sh instalar.sh; do
    cp "$tmp/servidor/$script" "$DIR/bin/$script.novo"
    chmod 755 "$DIR/bin/$script.novo"
    mv -f "$DIR/bin/$script.novo" "$DIR/bin/$script"
  done
  rm -r "$tmp"
}

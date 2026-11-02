#!/bin/bash
# Builds the Linux packages (decision 140) into dist/: kaladrius_<version>-1_amd64.deb,
# kaladrius-<version>-1.x86_64.rpm and their SHA256SUMS, with nFPM in a container pinned by
# digest.
#   deploy/pacote/gerar.sh                  the version of pyproject.toml and its public image,
#                                           pinned by the digest published on ghcr.io
#   deploy/pacote/gerar.sh --imagem IMAGEM [--versao X.Y.Z]
#                                           another image (tests: one built on this machine),
#                                           under another version (tests of an update)
set -euo pipefail
cd "$(dirname "$0")/../.."

NFPM=goreleaser/nfpm:v2.48.0@sha256:d57a1452e7a019896b355f7b1ec67262278f6c503631f652d4fce7aef9ac8df7
VERSAO=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
imagem=""
while [ $# -gt 0 ]; do
  case "$1" in
    --imagem) imagem=${2:?}; shift 2 ;;
    --versao) VERSAO=${2:?}; shift 2 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$imagem" ]; then
  digest=$(docker buildx imagetools inspect "ghcr.io/facchini-miguel/kaladrius:$VERSAO" \
    --format '{{json .Manifest}}' | python3 -c "import json, sys; print(json.load(sys.stdin)['digest'])")
  imagem="ghcr.io/facchini-miguel/kaladrius:$VERSAO@$digest"
fi

mkdir -p dist
printf 'VERSAO=%s\nIMAGEM=%s\n' "$VERSAO" "$imagem" >dist/pacote-linux
for formato in deb rpm; do
  docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/src" -w /src -e VERSAO="$VERSAO" \
    "$NFPM" package --config deploy/pacote/nfpm.yaml --packager "$formato" --target dist/
done
(cd dist && sha256sum "kaladrius_${VERSAO}-1_amd64.deb" "kaladrius-${VERSAO}-1.x86_64.rpm" >SHA256SUMS)
echo "Imagem: $imagem"
ls -l dist/*"$VERSAO"* dist/SHA256SUMS

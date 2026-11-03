#!/bin/bash
# Builds the Linux packages (decision 140) into dist/: kaladrius_<version>-1_amd64.deb,
# kaladrius-<version>-1.x86_64.rpm, kaladrius-<version>-1-x86_64.pkg.tar.zst (Arch Linux) and
# their SHA256SUMS, with nFPM in a container pinned by
# digest.
#   deploy/pacote/gerar.sh [--commit SHA]   the version of pyproject.toml and its public image,
#                                           pinned by the digest published on ghcr.io; with
#                                           --commit (CI's release), only when that image was
#                                           built from that commit
#   deploy/pacote/gerar.sh --imagem IMAGEM [--versao X.Y.Z]
#                                           another image (tests: one built on this machine),
#                                           under another version (tests of an update)
set -euo pipefail
cd "$(dirname "$0")/../.."

NFPM=goreleaser/nfpm:v2.48.0@sha256:d57a1452e7a019896b355f7b1ec67262278f6c503631f652d4fce7aef9ac8df7
VERSAO=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
imagem=""
commit=""
while [ $# -gt 0 ]; do
  case "$1" in
    --imagem) imagem=${2:?}; shift 2 ;;
    --versao) VERSAO=${2:?}; shift 2 ;;
    --commit) commit=${2:?}; shift 2 ;;
    *) echo "Opção desconhecida: $1" >&2; exit 2 ;;
  esac
done
digest_de() {
  docker buildx imagetools inspect "ghcr.io/facchini-miguel/kaladrius:$1" \
    --format '{{json .Manifest}}' | python3 -c "import json, sys; print(json.load(sys.stdin)['digest'])"
}
if [ -z "$imagem" ]; then
  digest=$(digest_de "$VERSAO")
  imagem="ghcr.io/facchini-miguel/kaladrius:$VERSAO@$digest"
  # The version's tag points to its first image and is never moved (ci.yml): a release retried
  # on a later commit of the same version would ship that commit's scripts and Compose file with
  # the older image.
  if [ -n "$commit" ] && [ "$(digest_de "${commit::12}")" != "$digest" ]; then
    echo "A imagem $VERSAO foi publicada por outro commit, não por ${commit::12}: suba a versão em pyproject.toml e releases.yaml." >&2
    exit 1
  fi
fi

mkdir -p dist
printf 'VERSAO=%s\nIMAGEM=%s\n' "$VERSAO" "$imagem" >dist/pacote-linux
for formato in deb rpm archlinux; do
  docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/src" -w /src -e VERSAO="$VERSAO" \
    "$NFPM" package --config deploy/pacote/nfpm.yaml --packager "$formato" --target dist/
done
(cd dist && sha256sum "kaladrius_${VERSAO}-1_amd64.deb" "kaladrius-${VERSAO}-1.x86_64.rpm" \
  "kaladrius-${VERSAO}-1-x86_64.pkg.tar.zst" >SHA256SUMS)
echo "Imagem: $imagem"
ls -l dist/*"$VERSAO"* dist/SHA256SUMS

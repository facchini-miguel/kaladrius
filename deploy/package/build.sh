#!/bin/bash
# Builds the Linux packages (decision 140) into dist/: kaladrius_<version>-1_amd64.deb,
# kaladrius-<version>-1.x86_64.rpm, kaladrius-<version>-1-x86_64.pkg.tar.zst (Arch Linux) and
# their SHA256SUMS, with nFPM in a container pinned by
# digest.
#   deploy/package/build.sh [--commit SHA]   the version of pyproject.toml and its public image,
#                                            pinned by the digest published on ghcr.io; with
#                                            --commit (CI's release), only when that image was
#                                            built from that commit (its revision label)
#   deploy/package/build.sh --image IMAGE [--version X.Y.Z]
#                                            another image (tests: one built on this machine),
#                                            under another version (tests of an update)
set -euo pipefail
cd "$(dirname "$0")/../.."

NFPM=goreleaser/nfpm:v2.48.0@sha256:d57a1452e7a019896b355f7b1ec67262278f6c503631f652d4fce7aef9ac8df7
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
image=""
commit=""
while [ $# -gt 0 ]; do
  case "$1" in
    --image) image=${2:?}; shift 2 ;;
    --version) VERSION=${2:?}; shift 2 ;;
    --commit) commit=${2:?}; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$image" ]; then
  digest=$(docker buildx imagetools inspect "ghcr.io/facchini-miguel/kaladrius:$VERSION" \
    --format '{{json .Manifest}}' | python3 -c "import json, sys; print(json.load(sys.stdin)['digest'])")
  image="ghcr.io/facchini-miguel/kaladrius:$VERSION@$digest"
  # The version's tag points to its first image and is never moved (ci.yml): a release retried
  # on a later commit of the same version would ship that commit's scripts and Compose file with
  # the older image. The commit is the one the image records (ci.yml labels it), not its sha tag:
  # rebuilding the same commit moves that tag to a new digest, never the version's.
  if [ -n "$commit" ]; then
    revision=$(docker buildx imagetools inspect "$image" --format '{{json .Image}}' | python3 -c \
      "import json, sys; print(json.load(sys.stdin)['config'].get('Labels', {}).get('org.opencontainers.image.revision', ''))")
    if [ "$revision" != "$commit" ]; then
      echo "Image $VERSION was published by commit ${revision:-(without the org.opencontainers.image.revision label)}, not by $commit: raise the version in pyproject.toml and releases.yaml." >&2
      exit 1
    fi
  fi
fi

mkdir -p dist
printf 'VERSION=%s\nIMAGE=%s\n' "$VERSION" "$image" >dist/linux-package
for format in deb rpm archlinux; do
  docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/src" -w /src -e VERSION="$VERSION" \
    "$NFPM" package --config deploy/package/nfpm.yaml --packager "$format" --target dist/
done
(cd dist && sha256sum "kaladrius_${VERSION}-1_amd64.deb" "kaladrius-${VERSION}-1.x86_64.rpm" \
  "kaladrius-${VERSION}-1-x86_64.pkg.tar.zst" >SHA256SUMS)
echo "Image: $image"
ls -l dist/*"$VERSION"* dist/SHA256SUMS

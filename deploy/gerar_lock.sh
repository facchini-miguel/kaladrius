#!/bin/bash
# Generates the dependency locks (decision 136): requirements.txt and requirements-dev.txt from
# their .in files, and deploy/pip-tools.txt, the lock of the tool itself, every package pinned
# to an exact version and hashed. pip-compile runs in the official image of the Python of
# .python-version (decision 127), the one CI and the production image install with, since a
# lock depends on the interpreter it is resolved for. Pins already in a lock are kept: only
# what a .in file changed is resolved again.
# Usage, from anywhere in the repository (needs Docker):
#   deploy/gerar_lock.sh              regenerates the locks after a .in file changes
#   deploy/gerar_lock.sh --verificar  only checks them (CI): fails if regenerating would
#                                     change a package or version, so a .in edited without
#                                     its lock, or one lock updated without the other, never
#                                     gets merged
set -euo pipefail

RAIZ=$(cd "$(dirname "$0")/.." && pwd)
VERSAO=$(cat "$RAIZ/.python-version")
LOCKS=(deploy/pip-tools.txt requirements.txt requirements-dev.txt)
ARQUIVOS=(deploy/pip-tools.in requirements.in requirements-dev.in "${LOCKS[@]}")

case "${1:-}" in
  "") PASTA=$RAIZ ;;
  --verificar)
    PASTA=$(mktemp -d)
    trap 'rm -rf "$PASTA"' EXIT
    mkdir -p "$PASTA/deploy"
    for arquivo in "${ARQUIVOS[@]}"; do cp "$RAIZ/$arquivo" "$PASTA/$arquivo"; done
    ;;
  *)
    echo "Uso: $0 [--verificar]" >&2
    exit 2
    ;;
esac

# pip-tools itself is installed from its hashed lock. requirements-dev.in reads the
# production lock as a constraint, so it is compiled after it.
COMPILAR="pip-compile --quiet --generate-hashes --strip-extras"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$PASTA:/w" -w /w "python:$VERSAO-slim" sh -ec "
    pip install --quiet --user --no-warn-script-location --no-deps -r deploy/pip-tools.txt
    export PATH=\$HOME/.local/bin:\$PATH
    $COMPILAR --allow-unsafe deploy/pip-tools.in
    $COMPILAR requirements.in
    $COMPILAR requirements-dev.in"

# Packages and versions only: the hashes of a version change when its project uploads one more
# file for it (a wheel for a newer Python), and comments vary with the pip-tools that wrote
# them (Dependabot uses its own). tests/test_dependencias.py checks every package has hashes
# and that both locks agree on them.
pinos() { grep -E '^[A-Za-z0-9._-]+==' "$1" | sed 's/ .*//' | sort; }

if [ "$PASTA" != "$RAIZ" ]; then
  desatualizado=0
  for lock in "${LOCKS[@]}"; do
    diff -u --label "$lock (no repositório)" --label "$lock (gerado agora)" \
      <(pinos "$RAIZ/$lock") <(pinos "$PASTA/$lock") || desatualizado=1
  done
  if [ "$desatualizado" = 1 ]; then
    echo "Os locks não batem com os .in: rode deploy/gerar_lock.sh e faça commit do resultado." >&2
    exit 1
  fi
  echo "Locks em dia com os .in."
fi

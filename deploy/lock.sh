#!/bin/bash
# Generates the dependency locks (decision 136): requirements.txt and requirements-dev.txt from
# their .in files, and deploy/pip-tools.txt, the lock of the tool itself, every package pinned
# to an exact version and hashed. pip-compile runs in the official image of the Python of
# .python-version (decision 127), the one CI and the production image install with, since a
# lock depends on the interpreter it is resolved for. Pins already in a lock are kept: only
# what a .in file changed is resolved again.
# Usage, from anywhere in the repository (needs Docker):
#   deploy/lock.sh          regenerates the locks after a .in file changes
#   deploy/lock.sh --check  only checks them (CI): fails if regenerating would change a package
#                           or version, so a .in edited without its lock, or one lock updated
#                           without the other, never gets merged
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
IMAGE=$(sed -n 's/^FROM \(python:[^ ]*\).*/\1/p' "$ROOT/Dockerfile")
if [ -z "$IMAGE" ]; then
  echo "The Dockerfile has no FROM python:… line" >&2
  exit 1
fi
LOCKS=(deploy/pip-tools.txt requirements.txt requirements-dev.txt)
FILES=(deploy/pip-tools.in requirements.in requirements-dev.in "${LOCKS[@]}")

case "${1:-}" in
  "") WORK=$ROOT ;;
  --check)
    WORK=$(mktemp -d)
    trap 'rm -rf "$WORK"' EXIT
    mkdir -p "$WORK/deploy"
    for file in "${FILES[@]}"; do cp "$ROOT/$file" "$WORK/$file"; done
    ;;
  *)
    echo "Usage: $0 [--check]" >&2
    exit 2
    ;;
esac

# pip-tools itself is installed from its hashed lock. requirements-dev.in reads the
# production lock as a constraint, so it is compiled after it.
COMPILE="pip-compile --quiet --generate-hashes --strip-extras"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$WORK:/w" -w /w "$IMAGE" sh -ec "
    pip install --quiet --user --no-warn-script-location --no-deps -r deploy/pip-tools.txt
    export PATH=\$HOME/.local/bin:\$PATH
    $COMPILE --allow-unsafe deploy/pip-tools.in
    $COMPILE requirements.in
    $COMPILE requirements-dev.in"

# Packages and versions only: the hashes of a version change when its project uploads one more
# file for it (a wheel for a newer Python), and comments vary with the pip-tools that wrote
# them (Dependabot uses its own). tests/test_dependencies.py checks every package has hashes
# and that both locks agree on them.
pins() { grep -E '^[A-Za-z0-9._-]+==' "$1" | sed 's/ .*//' | sort; }

if [ "$WORK" != "$ROOT" ]; then
  outdated=0
  for lock in "${LOCKS[@]}"; do
    diff -u --label "$lock (in the repository)" --label "$lock (generated now)" \
      <(pins "$ROOT/$lock") <(pins "$WORK/$lock") || outdated=1
  done
  if [ "$outdated" = 1 ]; then
    echo "The locks do not match the .in files: run deploy/lock.sh and commit the result." >&2
    exit 1
  fi
  echo "Locks up to date with the .in files."
fi

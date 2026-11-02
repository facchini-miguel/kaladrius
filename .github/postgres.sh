#!/usr/bin/env bash
# CI's PostgreSQL, for ci.yml and migracoes.yml: production's image and digest (decision 138),
# read from deploy/docker-compose.prod.yml, so a Dependabot pull request for that file is tested
# on the digest it proposes. Not a "services:" entry, which cannot read a file. Database, user
# and password come from the job's POSTGRES_* variables.
#
#   .github/postgres.sh iniciar   # starts it, in the background
#   .github/postgres.sh esperar   # waits until it accepts connections (the job installs the
#                                 # rest in between)
set -euo pipefail

case "${1:-}" in
  iniciar)
    imagem=$(sed -n 's/^ *image: *\(postgres:[^ ]*\).*/\1/p' deploy/docker-compose.prod.yml)
    echo "$imagem"
    docker run -d --name postgres -p 5432:5432 -e POSTGRES_DB="$POSTGRES_DB" \
      -e POSTGRES_USER="$POSTGRES_USER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
      --health-cmd "pg_isready -U $POSTGRES_USER" --health-interval 2s "$imagem"
    ;;
  esperar)
    timeout 120 sh -c 'until [ "$(docker inspect -f "{{.State.Health.Status}}" postgres)" = healthy ]; do sleep 1; done'
    ;;
  *)
    echo "uso: $0 iniciar|esperar" >&2
    exit 2
    ;;
esac

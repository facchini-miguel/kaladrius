# Documentation site (decision 067): Docusaurus builds the static pages, Caddy serves them.
# Build from the repository root, because the user manual comes from docs/<lang>/manual:
#   docker build -f website/Dockerfile -t kaladrius-docs .
FROM node:20-alpine AS build
WORKDIR /repo/website
COPY website/package.json website/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY docs/ /repo/docs/
COPY website/ ./
RUN npm run build

FROM caddy:2-alpine
COPY website/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /repo/website/build /srv
EXPOSE 80

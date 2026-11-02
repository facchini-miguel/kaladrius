# Documentation site (decisions 067 and 073): Docusaurus builds the static pages, Caddy serves them.
#   docker build -t kaladrius-docs docs
FROM node:26-alpine@sha256:c6ad9e9c1d80f6eb607c26b4b0a132ff7a2344fad1c78ea3baa2a7d4c8de6d94 AS build
WORKDIR /site
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . ./
RUN npm run build

FROM caddy:2-alpine@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /site/build /srv
EXPOSE 80

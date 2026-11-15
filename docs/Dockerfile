# Documentation site (decisions 067 and 073): Docusaurus builds the static pages, Caddy serves them.
#   docker build -t kaladrius-docs docs
FROM node:26-alpine@sha256:c6ad9e9c1d80f6eb607c26b4b0a132ff7a2344fad1c78ea3baa2a7d4c8de6d94 AS build
WORKDIR /site
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . ./
RUN npm run build

FROM caddy:2-alpine@sha256:f6228111e5fafa1a5238258d0858e103f10599b8d1659a146e7726681a002bb9
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /site/build /srv
EXPOSE 80

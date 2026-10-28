# Documentation site (decisions 067 and 073): Docusaurus builds the static pages, Caddy serves them.
#   docker build -t kaladrius-docs docs
FROM node:20-alpine AS build
WORKDIR /site
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . ./
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /site/build /srv
EXPOSE 80

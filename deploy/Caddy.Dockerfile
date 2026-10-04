# Builds the Mini App and serves it with Caddy (automatic HTTPS).
# Build context: repository root.

FROM node:22-alpine AS webapp
WORKDIR /w
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY webapp/ ./
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=webapp /w/dist /srv

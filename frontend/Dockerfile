FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

# Checks both nginx itself and the reverse-proxied path to the backend (/api/v1/health via
# nginx.conf.template's location /api/) in one command - the same path the browser actually uses,
# so this also catches a broken proxy config or a dead backend, not just a dead nginx.
#
# 127.0.0.1, never `localhost`: getaddrinfo orders ::1 ahead of 127.0.0.1 per RFC 6724 (precedence
# 50 vs 35) regardless of /etc/hosts order, and busybox wget connects to the first address only
# instead of trying the rest. `listen 80;` binds IPv4 only, so `localhost` here is a guaranteed
# connection-refused on every install - reported unhealthy while the app served fine.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ && wget -q -O /dev/null http://127.0.0.1/api/v1/health

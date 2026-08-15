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
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost/ && wget -q -O /dev/null http://localhost/api/v1/health

# TransferIQ web image: Angular SPA served by nginx, which also reverse-proxies /api to the API container.
# Build context is frontend/:
#   docker build -t transferiq-web frontend
#   docker run --rm -p 8080:8080 -e API_UPSTREAM=http://host.docker.internal:8000 transferiq-web
# API_UPSTREAM is read at container start (nginx envsubst template), so one image works in every environment:
#   docker compose -> http://api:8000      Azure Container Apps -> http://<api-app-name> (internal ingress)

# ---- Build stage ----
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
# Copy only build inputs: a COPY . . would overwrite the Linux node_modules with any local (e.g. Windows) one.
COPY angular.json tsconfig.json tsconfig.app.json ./
COPY src ./src
COPY public ./public
RUN npx ng build --configuration production

# ---- Runtime stage (non-root nginx, listens on 8080) ----
FROM nginxinc/nginx-unprivileged:1.27-alpine

ENV API_UPSTREAM=http://api:8000

# Rendered to /etc/nginx/conf.d/default.conf by the image's entrypoint (only defined env vars are substituted).
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist/transferiq-web/browser/ /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1

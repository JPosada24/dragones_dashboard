# Imagen de PRODUCCIÓN del panel: Angular compilado y servido por Caddy (HTTPS automático y proxy de /api).
# En desarrollo no se usa: docker-compose.yml corre `ng serve`.

# ---- Etapa 1: compilar ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npx ng build --configuration production

# ---- Etapa 2: servir ----
FROM caddy:2.8.4-alpine
COPY --from=build /app/dist/frontend/browser /srv/panel
# El Caddyfile llega montado desde deploy/Caddyfile (así se ajusta sin reconstruir la imagen).
EXPOSE 80 443

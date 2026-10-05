# syntax=docker/dockerfile:1

# --- Etapa 1: compilación del frontend ---
FROM node:20-alpine AS build
WORKDIR /web
# CA opcionales de docker/certs/*.crt (redes con inspección HTTPS).
COPY docker/certs/ /tmp/certs/
RUN cat /tmp/certs/*.crt > /tmp/extra-ca.pem 2>/dev/null || true
ENV NODE_EXTRA_CA_CERTS=/tmp/extra-ca.pem
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Vacío: el frontend usa rutas relativas del mismo origen (nginx hace de proxy).
ENV VITE_API_URL=""
RUN npm run build

# --- Etapa 2: nginx ---
FROM nginx:alpine AS runtime
RUN rm /etc/nginx/conf.d/default.conf
COPY docker/nginx.conf /etc/nginx/conf.d/emotv.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

# syntax=docker/dockerfile:1
#
# Multi-stage build for the DataSentinel dashboard (React/Vite/TypeScript).
# The build output is a static bundle (dist/) — there is no server-side
# code to run — so the runtime stage is a minimal nginx image serving
# static files rather than a Node process. That's both lighter and simpler
# than `vite preview` (which is meant for local smoke-testing a build, not
# for serving a container long-term).

# ---- Build stage ----
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines VITE_* variables into the bundle at build time (see
# src/lib/api-client.ts), so this has to be a build ARG, not a runtime
# environment variable — changing it requires rebuilding this image.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---- Runtime stage: serve the static dist/ output ----
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html

# SPA fallback: unknown paths (client-side routes from react-router-dom)
# must serve index.html instead of a 404.
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80

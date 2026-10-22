FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
# The build version (set by the build-images workflow), served as /version.txt.
ARG APP_VERSION=dev
RUN npm run build && echo "$APP_VERSION" > dist/version.txt

FROM nginxinc/nginx-unprivileged:1.27-alpine
# The base image lags behind Alpine security fixes; pull them in, then drop root again.
USER root
RUN apk upgrade --no-cache
USER 101
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1

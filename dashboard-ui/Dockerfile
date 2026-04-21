FROM node:24-alpine AS build
WORKDIR /app

COPY dashboard-ui/package*.json ./
RUN npm ci

COPY dashboard-ui ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY dashboard-ui/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY dashboard-ui/runtime-config.template.js /usr/share/nginx/html/runtime-config.template.js
COPY dashboard-ui/docker-entrypoint.d/40-configure-dashboard.sh /docker-entrypoint.d/40-configure-dashboard.sh
RUN chmod +x /docker-entrypoint.d/40-configure-dashboard.sh

EXPOSE 80

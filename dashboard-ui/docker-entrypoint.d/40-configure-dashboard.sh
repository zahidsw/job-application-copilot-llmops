#!/bin/sh
set -eu

api_upstream="${API_UPSTREAM_URL:-http://api:8080}"
tool_upstream="${TOOL_UPSTREAM_URL:-http://mcp:8081}"
grafana_url="${PUBLIC_GRAFANA_URL:-http://127.0.0.1:3001}"
mlflow_url="${PUBLIC_MLFLOW_URL:-http://127.0.0.1:5001}"
prometheus_url="${PUBLIC_PROMETHEUS_URL:-http://127.0.0.1:9091}"
api_ready_url="${PUBLIC_API_READY_URL:-/ready}"
tool_ready_url="${PUBLIC_TOOL_READY_URL:-/tool-api/ready}"
entra_auth_enabled="${PUBLIC_ENTRA_AUTH_ENABLED:-false}"
session_absolute_timeout_seconds="${PUBLIC_SESSION_ABSOLUTE_TIMEOUT_SECONDS:-1800}"
session_idle_timeout_seconds="${PUBLIC_SESSION_IDLE_TIMEOUT_SECONDS:-900}"
session_refresh_interval_seconds="${PUBLIC_SESSION_REFRESH_INTERVAL_SECONDS:-300}"

sed \
  -e "s|__API_UPSTREAM_URL__|${api_upstream}|g" \
  -e "s|__TOOL_UPSTREAM_URL__|${tool_upstream}|g" \
  /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

sed \
  -e "s|__API_BASE_URL__||g" \
  -e "s|__TOOL_BASE_URL__|/tool-api|g" \
  -e "s|__GRAFANA_URL__|${grafana_url}|g" \
  -e "s|__MLFLOW_URL__|${mlflow_url}|g" \
  -e "s|__PROMETHEUS_URL__|${prometheus_url}|g" \
  -e "s|__API_READY_URL__|${api_ready_url}|g" \
  -e "s|__TOOL_READY_URL__|${tool_ready_url}|g" \
  -e "s|__ENTRA_AUTH_ENABLED__|${entra_auth_enabled}|g" \
  -e "s|__SESSION_ABSOLUTE_TIMEOUT_SECONDS__|${session_absolute_timeout_seconds}|g" \
  -e "s|__SESSION_IDLE_TIMEOUT_SECONDS__|${session_idle_timeout_seconds}|g" \
  -e "s|__SESSION_REFRESH_INTERVAL_SECONDS__|${session_refresh_interval_seconds}|g" \
  /usr/share/nginx/html/runtime-config.template.js > /usr/share/nginx/html/runtime-config.js

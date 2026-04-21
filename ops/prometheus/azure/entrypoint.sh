#!/bin/sh
set -eu

api_target="${API_METRICS_TARGET:-api:8080}"
api_scheme="${API_METRICS_SCHEME:-http}"
mcp_target="${MCP_METRICS_TARGET:-mcp:8081}"
mcp_scheme="${MCP_METRICS_SCHEME:-http}"

sed \
  -e "s|__API_METRICS_TARGET__|${api_target}|g" \
  -e "s|__API_METRICS_SCHEME__|${api_scheme}|g" \
  -e "s|__MCP_METRICS_TARGET__|${mcp_target}|g" \
  -e "s|__MCP_METRICS_SCHEME__|${mcp_scheme}|g" \
  /etc/prometheus/prometheus.yml.template > /etc/prometheus/prometheus.yml

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.console.libraries=/usr/share/prometheus/console_libraries \
  --web.console.templates=/usr/share/prometheus/consoles

#!/bin/sh
set -eu

prometheus_url="${PROMETHEUS_URL:-http://prometheus:9090}"

sed \
  -e "s|__PROMETHEUS_URL__|${prometheus_url}|g" \
  /etc/grafana/provisioning/datasources/datasource.template.yml > /etc/grafana/provisioning/datasources/datasource.yml

exec /run.sh

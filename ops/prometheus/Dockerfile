FROM prom/prometheus:latest

USER root
COPY ops/prometheus/azure/prometheus.yml.template /etc/prometheus/prometheus.yml.template
COPY ops/prometheus/azure/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

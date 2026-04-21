FROM grafana/grafana:latest

USER root
COPY ops/grafana/provisioning/dashboards /etc/grafana/provisioning/dashboards
COPY ops/grafana/azure/datasource.template.yml /etc/grafana/provisioning/datasources/datasource.template.yml
COPY ops/grafana/dashboards /var/lib/grafana/dashboards
COPY ops/grafana/azure/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

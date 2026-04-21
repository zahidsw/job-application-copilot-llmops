#!/usr/bin/env bash
set -euo pipefail

deployment_environment="${DEPLOYMENT_ENVIRONMENT:?DEPLOYMENT_ENVIRONMENT is required}"
resource_group="${AZURE_RESOURCE_GROUP:-job-application-copilot-${deployment_environment}-rg}"
location="${AZURE_LOCATION:-switzerlandnorth}"
base_name="${AZURE_BASE_NAME:-jobappcopilot${deployment_environment}}"
postgres_admin_user="${AZURE_POSTGRES_ADMIN_USER:-jobappadmin}"
postgres_admin_password="${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD is required}"
llm_provider="${LLM_PROVIDER:?LLM_PROVIDER is required}"
llm_base_url="${LLM_BASE_URL:?LLM_BASE_URL is required}"
llm_api_key="${LLM_API_KEY:?LLM_API_KEY is required}"
llm_model="${LLM_MODEL:?LLM_MODEL is required}"
mcp_client_auth_token="${MCP_CLIENT_AUTH_TOKEN:?MCP_CLIENT_AUTH_TOKEN is required}"
grafana_admin_password="${GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD is required}"

image_tag="${IMAGE_TAG:-${GITHUB_SHA:-manual}}"
llm_json_mode="${LLM_JSON_MODE:-json_object}"
llm_temperature="${LLM_TEMPERATURE:-0.2}"
llm_max_tokens="${LLM_MAX_TOKENS:-1400}"
request_timeout_seconds="${REQUEST_TIMEOUT_SECONDS:-60}"
smtp_host="${SMTP_HOST:-}"
smtp_port="${SMTP_PORT:-587}"
smtp_user="${SMTP_USER:-}"
smtp_password="${SMTP_PASSWORD:-}"
smtp_from="${SMTP_FROM:-}"

acr_name="$(echo "${base_name}acr" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-50)"
storage_account_name="$(echo "${base_name}files" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-24)"
container_apps_env_name="${AZURE_CONTAINER_APPS_ENVIRONMENT_NAME:-${base_name}-env}"
log_analytics_name="${base_name}-logs"
postgres_server_name="${base_name}-pg"
shared_deployment_name="jobapp-${deployment_environment}-shared"
apps_deployment_name="jobapp-${deployment_environment}-apps"

az group create \
  --name "${resource_group}" \
  --location "${location}" \
  --output none

az deployment group create \
  --name "${shared_deployment_name}" \
  --resource-group "${resource_group}" \
  --template-file ops/azure/main.bicep \
  --parameters \
    location="${location}" \
    baseName="${base_name}" \
    deploymentEnvironment="${deployment_environment}" \
    deployApps=false \
    containerRegistryName="${acr_name}" \
    containerAppsEnvironmentName="${container_apps_env_name}" \
    logAnalyticsWorkspaceName="${log_analytics_name}" \
    storageAccountName="${storage_account_name}" \
    postgresServerName="${postgres_server_name}" \
    postgresAdminUser="${postgres_admin_user}" \
    postgresAdminPassword="${postgres_admin_password}" \
  --output none

acr_login_server="$(az acr show --name "${acr_name}" --resource-group "${resource_group}" --query loginServer --output tsv)"
az acr login --name "${acr_name}"

app_image="${acr_login_server}/jobapp-app:${image_tag}"
dashboard_image="${acr_login_server}/jobapp-dashboard:${image_tag}"
mlflow_image="${acr_login_server}/jobapp-mlflow:${image_tag}"
prometheus_image="${acr_login_server}/jobapp-prometheus:${image_tag}"
grafana_image="${acr_login_server}/jobapp-grafana:${image_tag}"

docker build -t "${app_image}" -f Dockerfile .
docker push "${app_image}"

docker build -t "${dashboard_image}" -f dashboard-ui/Dockerfile .
docker push "${dashboard_image}"

docker build -t "${mlflow_image}" -f ops/mlflow/Dockerfile .
docker push "${mlflow_image}"

docker build -t "${prometheus_image}" -f ops/prometheus/Dockerfile .
docker push "${prometheus_image}"

docker build -t "${grafana_image}" -f ops/grafana/Dockerfile .
docker push "${grafana_image}"

az deployment group create \
  --name "${apps_deployment_name}" \
  --resource-group "${resource_group}" \
  --template-file ops/azure/main.bicep \
  --parameters \
    location="${location}" \
    baseName="${base_name}" \
    deploymentEnvironment="${deployment_environment}" \
    deployApps=true \
    containerRegistryName="${acr_name}" \
    containerAppsEnvironmentName="${container_apps_env_name}" \
    logAnalyticsWorkspaceName="${log_analytics_name}" \
    storageAccountName="${storage_account_name}" \
    postgresServerName="${postgres_server_name}" \
    postgresAdminUser="${postgres_admin_user}" \
    postgresAdminPassword="${postgres_admin_password}" \
    appImage="${app_image}" \
    dashboardImage="${dashboard_image}" \
    mlflowImage="${mlflow_image}" \
    prometheusImage="${prometheus_image}" \
    grafanaImage="${grafana_image}" \
    llmProvider="${llm_provider}" \
    llmBaseUrl="${llm_base_url}" \
    llmApiKey="${llm_api_key}" \
    llmModel="${llm_model}" \
    llmJsonMode="${llm_json_mode}" \
    llmTemperature="${llm_temperature}" \
    llmMaxTokens="${llm_max_tokens}" \
    requestTimeoutSeconds="${request_timeout_seconds}" \
    mcpClientAuthToken="${mcp_client_auth_token}" \
    grafanaAdminPassword="${grafana_admin_password}" \
    smtpHost="${smtp_host}" \
    smtpPort="${smtp_port}" \
    smtpUser="${smtp_user}" \
    smtpPassword="${smtp_password}" \
    smtpFrom="${smtp_from}" \
  --output none

outputs="$(az deployment group show --resource-group "${resource_group}" --name "${apps_deployment_name}" --query properties.outputs --output json)"

dashboard_url="$(echo "${outputs}" | jq -r '.dashboardUrl.value // empty')"
api_url="$(echo "${outputs}" | jq -r '.apiUrl.value // empty')"
mlflow_url="$(echo "${outputs}" | jq -r '.mlflowUrl.value // empty')"
grafana_url="$(echo "${outputs}" | jq -r '.grafanaUrl.value // empty')"
prometheus_url="$(echo "${outputs}" | jq -r '.prometheusUrl.value // empty')"

echo "Deployed ${deployment_environment}"
echo "Dashboard: ${dashboard_url}"
echo "API: ${api_url}"
echo "MLflow: ${mlflow_url}"
echo "Grafana: ${grafana_url}"
echo "Prometheus: ${prometheus_url}"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "## Azure Deployment (${deployment_environment})"
    echo ""
    echo "- Dashboard: ${dashboard_url}"
    echo "- API: ${api_url}"
    echo "- MLflow: ${mlflow_url}"
    echo "- Grafana: ${grafana_url}"
    echo "- Prometheus: ${prometheus_url}"
  } >> "${GITHUB_STEP_SUMMARY}"
fi

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
similar_job_search_provider="${SIMILAR_JOB_SEARCH_PROVIDER:-serpapi}"
similar_job_min_score="${SIMILAR_JOB_MIN_SCORE:-80}"
serpapi_api_key="${SERPAPI_API_KEY:-}"
langsmith_tracing="${LANGSMITH_TRACING:-false}"
langsmith_api_key="${LANGSMITH_API_KEY:-}"
langsmith_project="${LANGSMITH_PROJECT:-job-application-copilot-${deployment_environment}}"
langsmith_endpoint="${LANGSMITH_ENDPOINT:-https://api.smith.langchain.com}"
langsmith_workspace_id="${LANGSMITH_WORKSPACE_ID:-}"
langsmith_hide_inputs="${LANGSMITH_HIDE_INPUTS:-true}"
langsmith_hide_outputs="${LANGSMITH_HIDE_OUTPUTS:-true}"
smtp_host="${SMTP_HOST:-}"
smtp_port="${SMTP_PORT:-587}"
smtp_user="${SMTP_USER:-}"
smtp_password="${SMTP_PASSWORD:-}"
smtp_from="${SMTP_FROM:-}"
entra_auth_enabled="${ENTRA_AUTH_ENABLED:-false}"
entra_tenant_id="${ENTRA_TENANT_ID:-}"
entra_client_id="${ENTRA_CLIENT_ID:-}"
entra_client_secret="${ENTRA_CLIENT_SECRET:-}"
entra_allowed_group_ids="${ENTRA_ALLOWED_GROUP_IDS:-}"
entra_session_cookie_expiration="${ENTRA_SESSION_COOKIE_EXPIRATION:-00:30:00}"
entra_session_absolute_timeout_seconds="${ENTRA_SESSION_ABSOLUTE_TIMEOUT_SECONDS:-1800}"
entra_session_idle_timeout_seconds="${ENTRA_SESSION_IDLE_TIMEOUT_SECONDS:-900}"
entra_session_refresh_interval_seconds="${ENTRA_SESSION_REFRESH_INTERVAL_SECONDS:-300}"
entra_token_store_sas_url=""

if [[ "${entra_auth_enabled}" == "true" ]]; then
  : "${entra_tenant_id:?ENTRA_TENANT_ID is required when ENTRA_AUTH_ENABLED=true}"
  : "${entra_client_id:?ENTRA_CLIENT_ID is required when ENTRA_AUTH_ENABLED=true}"
  : "${entra_client_secret:?ENTRA_CLIENT_SECRET is required when ENTRA_AUTH_ENABLED=true}"
  : "${entra_allowed_group_ids:?ENTRA_ALLOWED_GROUP_IDS is required when ENTRA_AUTH_ENABLED=true}"
fi

retry() {
  local max_attempts=3
  local delay_seconds=20
  local attempt=1

  until "$@"; do
    if [ "${attempt}" -ge "${max_attempts}" ]; then
      return 1
    fi

    echo "Command failed on attempt ${attempt}/${max_attempts}. Retrying in ${delay_seconds}s: $*"
    sleep "${delay_seconds}"
    attempt=$((attempt + 1))
  done
}

acr_name="$(echo "${base_name}acr" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-50)"
storage_account_name="$(echo "${base_name}files" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-24)"
auth_token_container_name="entratokens"
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

if [[ "${entra_auth_enabled}" == "true" ]]; then
  storage_account_key="$(az storage account keys list --resource-group "${resource_group}" --account-name "${storage_account_name}" --query "[0].value" --output tsv)"
  sas_expiry="$(python -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) + timedelta(days=365 * 5)).strftime("%Y-%m-%dT%H:%MZ"))')"
  token_store_sas="$(az storage container generate-sas \
    --account-name "${storage_account_name}" \
    --account-key "${storage_account_key}" \
    --name "${auth_token_container_name}" \
    --permissions dlrwac \
    --expiry "${sas_expiry}" \
    --https-only \
    --output tsv)"
  entra_token_store_sas_url="https://${storage_account_name}.blob.core.windows.net/${auth_token_container_name}?${token_store_sas}"
fi

acr_login_server="$(az acr show --name "${acr_name}" --resource-group "${resource_group}" --query loginServer --output tsv)"
az acr login --name "${acr_name}"

app_image="${acr_login_server}/jobapp-app:${image_tag}"
dashboard_image="${acr_login_server}/jobapp-dashboard:${image_tag}"
mlflow_image="${acr_login_server}/jobapp-mlflow:${image_tag}"
prometheus_image="${acr_login_server}/jobapp-prometheus:${image_tag}"
grafana_image="${acr_login_server}/jobapp-grafana:${image_tag}"
entra_allowed_groups_json='[]'

if [[ "${entra_auth_enabled}" == "true" ]]; then
  entra_allowed_groups_json="$(printf '%s' "${entra_allowed_group_ids}" | tr ',' '\n' | sed '/^[[:space:]]*$/d' | jq -R . | jq -s .)"
fi

retry docker build -t "${app_image}" -f Dockerfile .
retry docker push "${app_image}"

retry docker build -t "${dashboard_image}" -f dashboard-ui/Dockerfile .
retry docker push "${dashboard_image}"

retry docker build -t "${mlflow_image}" -f ops/mlflow/Dockerfile .
retry docker push "${mlflow_image}"

retry docker build -t "${prometheus_image}" -f ops/prometheus/Dockerfile .
retry docker push "${prometheus_image}"

retry docker build -t "${grafana_image}" -f ops/grafana/Dockerfile .
retry docker push "${grafana_image}"

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
    similarJobSearchProvider="${similar_job_search_provider}" \
    similarJobMinScore="${similar_job_min_score}" \
    serpApiKey="${serpapi_api_key}" \
    langsmithTracing="${langsmith_tracing}" \
    langsmithApiKey="${langsmith_api_key}" \
    langsmithProject="${langsmith_project}" \
    langsmithEndpoint="${langsmith_endpoint}" \
    langsmithWorkspaceId="${langsmith_workspace_id}" \
    langsmithHideInputs="${langsmith_hide_inputs}" \
    langsmithHideOutputs="${langsmith_hide_outputs}" \
    mcpClientAuthToken="${mcp_client_auth_token}" \
    grafanaAdminPassword="${grafana_admin_password}" \
    smtpHost="${smtp_host}" \
    smtpPort="${smtp_port}" \
    smtpUser="${smtp_user}" \
    smtpPassword="${smtp_password}" \
    smtpFrom="${smtp_from}" \
    enableEntraProtection="${entra_auth_enabled}" \
    entraTenantId="${entra_tenant_id}" \
    entraClientId="${entra_client_id}" \
    entraClientSecret="${entra_client_secret}" \
    entraAllowedGroupIds="${entra_allowed_groups_json}" \
    entraTokenStoreSasUrl="${entra_token_store_sas_url}" \
    entraSessionCookieExpiration="${entra_session_cookie_expiration}" \
    entraSessionAbsoluteTimeoutSeconds="${entra_session_absolute_timeout_seconds}" \
    entraSessionIdleTimeoutSeconds="${entra_session_idle_timeout_seconds}" \
    entraSessionRefreshIntervalSeconds="${entra_session_refresh_interval_seconds}" \
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

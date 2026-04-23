# Azure Deployment

The best Azure fit for this project is `Azure Container Apps` plus a few managed backing services:

- `Azure Container Apps`
  - `dashboard`
  - `api`
  - `mcp`
  - `mlflow`
  - `prometheus`
  - `grafana`
- `Azure Container Registry` for the built images
- `Azure Database for PostgreSQL Flexible Server` for application state and MLflow metadata
- `Azure Files` for generated CVs, PDFs, reports, and MLflow artifacts
- `Log Analytics` for container logs

This keeps the architecture very close to the current Docker setup, but replaces the most important stateful local dependencies 
with managed Azure services.

## Why This Is The Recommended Azure Option

`Azure Container Apps` is the best fit here because the application is already split into container-friendly services, 
it does not need full Kubernetes control, and it benefits from simple ingress, scale rules, and managed revisions.

This is a better first cloud target than:

- `App Service`
  because the stack is multi-service and not just one web app
- `AKS`
  because it adds operational weight you do not need yet
- `Virtual Machines`
  because you would be rebuilding orchestration, ingress, and scaling by hand

## What Uses The Shared LLM Env

The local deployment script reads selected values from:

`C:\Users\marya\Documents\New project\multi-agent-research-llmops\.env`

The script maps these values into the Azure deployment:

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_JSON_MODE`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `REQUEST_TIMEOUT_SECONDS`
- optional `LANGSMITH_TRACING`
- optional `LANGSMITH_PROJECT`
- optional `LANGSMITH_ENDPOINT`
- optional `LANGSMITH_HIDE_INPUTS`
- optional `LANGSMITH_HIDE_OUTPUTS`

The API key is never written into the repo by the deployment script. It is passed to Azure as a secret.

## Local One-Time Requirements

Install:

- Azure CLI
- Docker Desktop
- an Azure subscription with permission to create resource groups, Container Apps, ACR, Storage, and PostgreSQL

Then sign in:

```powershell
az login
az account set --subscription "<your-subscription-name-or-id>"
```

## Local Deployment

From the project root:

```powershell
cd "C:\Users\marya\Documents\New project\job-application-copilot-llmops"
```

Run:

```powershell
.\ops\azure\deploy.ps1 `
  -EnvironmentName test `
  -Location "switzerlandnorth" `
  -SharedEnvPath "C:\Users\marya\Documents\New project\multi-agent-research-llmops\.env" `
  -PostgresAdminUser "jobappadmin" `
  -PostgresAdminPassword "<strong-password>" `
  -McpClientAuthToken "<shared-tool-token>" `
  -GrafanaAdminPassword "<grafana-password>" `
  -ImageTag "manual-001"
```

The script does this in order:

1. creates or updates the resource group
2. deploys shared Azure infrastructure first
3. reads the LLM settings from the shared `.env`
4. builds and pushes the five images to Azure Container Registry
5. deploys the Container Apps
6. prints the public URLs for dashboard, API, MLflow, Grafana, and Prometheus

The default local deployment now targets `test` and `switzerlandnorth`, because the current Azure subscription policy allows `polandcentral`, `spaincentral`, `germanywestcentral`, `switzerlandnorth`, and `swedencentral`.

## GitHub Actions CI/CD

The workflow file is:

`C:\Users\marya\Documents\New project\job-application-copilot-llmops\.github\workflows\azure-container-apps.yml`

It uses Azure OIDC login, so you do not need a long-lived publish profile.

The branch flow now works like a GitLab-style promotion pipeline:

1. `pull_request` into `main` runs validation only.
2. Pushes to `feature/**`, `feat/**`, `bugfix/**`, or `hotfix/**` run validation and then deploy `test`.
3. Pushes to `main` run validation and then deploy `prod`.
4. Manual dispatch can still deploy `test`, `prod`, or `both`.

Use GitHub Environments named `test` and `prod`. If you want production to pause for human approval after `main` passes validation, add a protection rule on the `prod` environment. If you want fully automatic production deployment, leave `prod` without required reviewers.

The current Azure for Students quota only allows one Container Apps Environment in the subscription. For that reason, `prod` can reuse the existing test Container Apps Environment by setting `AZURE_CONTAINER_APPS_ENVIRONMENT_NAME=jobappcopilottest-env` while still deploying separate `jobappcopilotprod-*` Container Apps.

Because test and prod can share that one Container Apps Environment, the deploy jobs use the same GitHub concurrency group. That keeps Azure environment updates sequential and avoids `ManagedEnvironmentOperationInProgress` failures.

### Validation Gates

Every branch deployment must pass the `Validate` job first. The validation job:

1. installs Python dependencies
2. compiles the Python package
3. runs pytest when a `tests` directory exists
4. validates `docker compose`
5. validates the Azure Bicep template

If any validation step fails, neither `test` nor `prod` deploys.

### Rerun The Pipeline

Use GitHub Actions when the project is pushed to GitHub:

1. Open the repository on GitHub.
2. Go to `Actions`.
3. Select `CI/CD To Azure Container Apps`.
4. Click `Run workflow`.
5. Pick `test`, `prod`, or `both`.
6. Leave `image_tag` empty unless you want a custom tag.

Use local Azure CLI when you want to deploy from this computer:

```powershell
.\ops\azure\deploy.ps1 `
  -EnvironmentName test `
  -ImageTag "test-manual-002" `
  -PostgresAdminPassword "<test-postgres-password>" `
  -McpClientAuthToken "<test-tool-token>" `
  -GrafanaAdminPassword "<test-grafana-password>"
```

```powershell
.\ops\azure\deploy.ps1 `
  -EnvironmentName prod `
  -ImageTag "prod-manual-001" `
  -PostgresAdminPassword "<prod-postgres-password>" `
  -McpClientAuthToken "<prod-tool-token>" `
  -GrafanaAdminPassword "<prod-grafana-password>"
```

`test` creates or updates `job-application-copilot-test-rg` and `jobappcopilottest-*` resources by default. `prod` creates or updates `job-application-copilot-prod-rg` and `jobappcopilotprod-*` resources by default.

### GitHub Repository Variables

Create these repository variables. The Azure naming variables are optional because the CI script defaults them per environment:

- `AZURE_RESOURCE_GROUP`
- `AZURE_LOCATION`
- `AZURE_BASE_NAME`
- `AZURE_CONTAINER_APPS_ENVIRONMENT_NAME`
- `AZURE_POSTGRES_ADMIN_USER`
- `LLM_JSON_MODE`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `REQUEST_TIMEOUT_SECONDS`
- `LANGSMITH_TRACING`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_HIDE_INPUTS`
- `LANGSMITH_HIDE_OUTPUTS`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_FROM`

Default values if omitted are `job-application-copilot-<environment>-rg`, `switzerlandnorth`, `jobappcopilot<environment>`, and `jobappadmin`.

### GitHub Repository Secrets

Create these repository secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `POSTGRES_ADMIN_PASSWORD`
- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LANGSMITH_API_KEY`
- `MCP_CLIENT_AUTH_TOKEN`
- `GRAFANA_ADMIN_PASSWORD`
- `SMTP_PASSWORD`

For the LLM secrets, copy the values from your shared `.env` into GitHub secrets instead of committing them anywhere.

## Azure OIDC Setup For GitHub Actions

Create an Azure app registration or user-assigned identity for GitHub Actions, grant it access to the target resource group, and configure a federated credential for your GitHub repository and branch.

After that, store:

- the app or identity client ID as `AZURE_CLIENT_ID`
- the Azure tenant ID as `AZURE_TENANT_ID`
- the subscription ID as `AZURE_SUBSCRIPTION_ID`

## Architecture Notes

- The API and MLflow mount the same Azure Files share.
- The MCP tool service stays private inside the Container Apps environment.
- The dashboard reverse-proxies the API and tool service internally.
- Grafana and Prometheus run as dedicated Container Apps so the operator dashboard can link to them directly.
- The current Bicep enables PostgreSQL public networking with the Azure-services firewall rule for a fast first deployment.

That last point is convenient, but it is not the final security posture. The next hardening step is to move the Container Apps environment and PostgreSQL server behind private networking.

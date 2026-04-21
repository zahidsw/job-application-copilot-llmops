param(
    [ValidateSet("test", "prod")]
    [string]$EnvironmentName = "test",
    [string]$ResourceGroup = "",
    [string]$Location = "switzerlandnorth",
    [string]$BaseName = "",
    [string]$ContainerAppsEnvironmentName = "",
    [string]$SharedEnvPath = "C:\Users\marya\Documents\New project\multi-agent-research-llmops\.env",
    [string]$PostgresAdminUser = "jobappadmin",
    [string]$PostgresAdminPassword,
    [string]$McpClientAuthToken = "change-me-api-token",
    [string]$GrafanaAdminPassword = "ChangeThisGrafanaPassword!",
    [string]$SmtpHost = "",
    [string]$SmtpPort = "587",
    [string]$SmtpUser = "",
    [string]$SmtpPassword = "",
    [string]$SmtpFrom = "",
    [string]$ImageTag = "manual"
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install it first."
    }
}

function Resolve-AzCommand {
    $command = Get-Command "az" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $fallback = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
    if (Test-Path -LiteralPath $fallback) {
        return $fallback
    }

    throw "Required command 'az' was not found. Install Azure CLI or add it to PATH."
}

function Read-EnvFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "The environment file '$Path' was not found."
    }

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("#")) {
            continue
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        $values[$key] = $value
    }

    return $values
}

function Normalize-Name {
    param(
        [string]$Value,
        [int]$MaxLength = 24
    )

    $normalized = ($Value.ToLowerInvariant() -replace "[^a-z0-9]", "")
    if ($normalized.Length -gt $MaxLength) {
        return $normalized.Substring(0, $MaxLength)
    }
    return $normalized
}

function Invoke-AzDeployment {
    param(
        [string]$DeploymentName,
        [string]$TemplateFile,
        [hashtable]$Parameters
    )

    $parameterArgs = @()
    foreach ($entry in $Parameters.GetEnumerator()) {
        $parameterArgs += @("--parameters", "$($entry.Key)=$($entry.Value)")
    }

    & $script:AzCommand deployment group create `
        --name $DeploymentName `
        --resource-group $ResourceGroup `
        --template-file $TemplateFile `
        @parameterArgs `
        --output json | Out-Null
}

Require-Command -Name "docker"
$script:AzCommand = Resolve-AzCommand

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$templateFile = Join-Path $PSScriptRoot "main.bicep"
$sharedEnv = Read-EnvFile -Path $SharedEnvPath
$environmentLabel = $EnvironmentName.ToLowerInvariant()

if (-not $ResourceGroup) {
    $ResourceGroup = "job-application-copilot-$environmentLabel-rg"
}

if (-not $BaseName) {
    $BaseName = "jobappcopilot$environmentLabel"
}

if (-not $PostgresAdminPassword) {
    throw "Provide -PostgresAdminPassword so the Flexible Server can be created."
}

$acrName = Normalize-Name -Value "${BaseName}acr" -MaxLength 50
$storageAccountName = Normalize-Name -Value "${BaseName}files" -MaxLength 24
$containerAppsEnvironmentName = if ($ContainerAppsEnvironmentName) { $ContainerAppsEnvironmentName } else { "${BaseName}-env" }
$logAnalyticsWorkspaceName = "${BaseName}-logs"
$postgresServerName = "${BaseName}-pg"
$sharedDeploymentName = "jobapp-$environmentLabel-shared"
$appsDeploymentName = "jobapp-$environmentLabel-apps"

$llmProvider = $sharedEnv["LLM_PROVIDER"]
$llmBaseUrl = $sharedEnv["LLM_BASE_URL"]
$llmApiKey = $sharedEnv["LLM_API_KEY"]
$llmModel = $sharedEnv["LLM_MODEL"]
$llmJsonMode = if ($sharedEnv.ContainsKey("LLM_JSON_MODE")) { $sharedEnv["LLM_JSON_MODE"] } else { "json_object" }
$llmTemperature = if ($sharedEnv.ContainsKey("LLM_TEMPERATURE")) { $sharedEnv["LLM_TEMPERATURE"] } else { "0.2" }
$llmMaxTokens = if ($sharedEnv.ContainsKey("LLM_MAX_TOKENS")) { $sharedEnv["LLM_MAX_TOKENS"] } else { "1400" }
$requestTimeoutSeconds = if ($sharedEnv.ContainsKey("REQUEST_TIMEOUT_SECONDS")) { $sharedEnv["REQUEST_TIMEOUT_SECONDS"] } else { "60" }

if (-not $llmApiKey) {
    throw "LLM_API_KEY was not found in '$SharedEnvPath'."
}

Write-Host "Creating or updating the resource group..."
& $AzCommand group create --name $ResourceGroup --location $Location --output none

Write-Host "Deploying shared Azure infrastructure..."
Invoke-AzDeployment -DeploymentName $sharedDeploymentName -TemplateFile $templateFile -Parameters @{
    location = $Location
    baseName = $BaseName
    deploymentEnvironment = $environmentLabel
    deployApps = "false"
    containerRegistryName = $acrName
    containerAppsEnvironmentName = $containerAppsEnvironmentName
    logAnalyticsWorkspaceName = $logAnalyticsWorkspaceName
    storageAccountName = $storageAccountName
    postgresServerName = $postgresServerName
    postgresAdminUser = $PostgresAdminUser
    postgresAdminPassword = $PostgresAdminPassword
}

$acrLoginServer = & $AzCommand acr show --name $acrName --resource-group $ResourceGroup --query loginServer --output tsv
if (-not $acrLoginServer) {
    throw "Could not resolve the Azure Container Registry login server for '$acrName'."
}

Write-Host "Logging into Azure Container Registry..."
& $AzCommand acr login --name $acrName

$images = @{
    app = "$acrLoginServer/jobapp-app:$ImageTag"
    dashboard = "$acrLoginServer/jobapp-dashboard:$ImageTag"
    mlflow = "$acrLoginServer/jobapp-mlflow:$ImageTag"
    prometheus = "$acrLoginServer/jobapp-prometheus:$ImageTag"
    grafana = "$acrLoginServer/jobapp-grafana:$ImageTag"
}

Write-Host "Building and pushing application images..."
docker build -t $images.app -f (Join-Path $projectRoot "Dockerfile") $projectRoot
docker push $images.app

docker build -t $images.dashboard -f (Join-Path $projectRoot "dashboard-ui\Dockerfile") $projectRoot
docker push $images.dashboard

docker build -t $images.mlflow -f (Join-Path $projectRoot "ops\mlflow\Dockerfile") $projectRoot
docker push $images.mlflow

docker build -t $images.prometheus -f (Join-Path $projectRoot "ops\prometheus\Dockerfile") $projectRoot
docker push $images.prometheus

docker build -t $images.grafana -f (Join-Path $projectRoot "ops\grafana\Dockerfile") $projectRoot
docker push $images.grafana

Write-Host "Deploying Container Apps..."
Invoke-AzDeployment -DeploymentName $appsDeploymentName -TemplateFile $templateFile -Parameters @{
    location = $Location
    baseName = $BaseName
    deploymentEnvironment = $environmentLabel
    deployApps = "true"
    containerRegistryName = $acrName
    containerAppsEnvironmentName = $containerAppsEnvironmentName
    logAnalyticsWorkspaceName = $logAnalyticsWorkspaceName
    storageAccountName = $storageAccountName
    postgresServerName = $postgresServerName
    postgresAdminUser = $PostgresAdminUser
    postgresAdminPassword = $PostgresAdminPassword
    appImage = $images.app
    dashboardImage = $images.dashboard
    mlflowImage = $images.mlflow
    prometheusImage = $images.prometheus
    grafanaImage = $images.grafana
    llmProvider = $llmProvider
    llmBaseUrl = $llmBaseUrl
    llmApiKey = $llmApiKey
    llmModel = $llmModel
    llmJsonMode = $llmJsonMode
    llmTemperature = $llmTemperature
    llmMaxTokens = $llmMaxTokens
    requestTimeoutSeconds = $requestTimeoutSeconds
    mcpClientAuthToken = $McpClientAuthToken
    grafanaAdminPassword = $GrafanaAdminPassword
    smtpHost = $SmtpHost
    smtpPort = $SmtpPort
    smtpUser = $SmtpUser
    smtpPassword = $SmtpPassword
    smtpFrom = $SmtpFrom
}

$outputs = & $AzCommand deployment group show `
    --resource-group $ResourceGroup `
    --name $appsDeploymentName `
    --query properties.outputs `
    --output json | ConvertFrom-Json

Write-Host ""
Write-Host "Azure deployment completed for environment '$environmentLabel'."
if ($outputs.dashboardUrl.value) {
    Write-Host "Dashboard:   $($outputs.dashboardUrl.value)"
}
if ($outputs.apiUrl.value) {
    Write-Host "API:         $($outputs.apiUrl.value)"
}
if ($outputs.mlflowUrl.value) {
    Write-Host "MLflow:      $($outputs.mlflowUrl.value)"
}
if ($outputs.grafanaUrl.value) {
    Write-Host "Grafana:     $($outputs.grafanaUrl.value)"
}
if ($outputs.prometheusUrl.value) {
    Write-Host "Prometheus:  $($outputs.prometheusUrl.value)"
}

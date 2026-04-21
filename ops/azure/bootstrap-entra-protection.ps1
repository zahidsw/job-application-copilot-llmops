param(
  [string]$AppDisplayName = 'job-application-copilot-suite',
  [string]$HomePageUrl = 'https://jobappcopilottest-dashboard.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io',
  [string[]]$RedirectUris = @(
    'https://jobappcopilottest-dashboard.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilottest-grafana.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilottest-mlflow.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilottest-prometheus.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilotprod-dashboard.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilotprod-grafana.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilotprod-mlflow.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback',
    'https://jobappcopilotprod-prometheus.kindmushroom-ed0dc553.switzerlandnorth.azurecontainerapps.io/.auth/login/aad/callback'
  )
)

$ErrorActionPreference = 'Stop'

$appRoles = @(
  @{
    allowedMemberTypes = @('User', 'Application')
    description = 'Full administrative access to the Job Application Copilot platform.'
    displayName = 'Job Application Copilot Admin'
    isEnabled = $true
    origin = 'Application'
    value = 'JobApplicationCopilot.Admin'
  },
  @{
    allowedMemberTypes = @('User', 'Application')
    description = 'Operational access to launch, review, and approve job application runs.'
    displayName = 'Job Application Copilot Operator'
    isEnabled = $true
    origin = 'Application'
    value = 'JobApplicationCopilot.Operator'
  },
  @{
    allowedMemberTypes = @('User', 'Application')
    description = 'Read-only access intended for future reporting and review scenarios.'
    displayName = 'Job Application Copilot Viewer'
    isEnabled = $true
    origin = 'Application'
    value = 'JobApplicationCopilot.Viewer'
  }
)

$groupDefinitions = @(
  @{ name = 'job-application-copilot-admins'; nickname = 'jobappcopilotadmins'; role = 'JobApplicationCopilot.Admin'; seedUser = $true },
  @{ name = 'job-application-copilot-operators'; nickname = 'jobappcopilotoperators'; role = 'JobApplicationCopilot.Operator'; seedUser = $false },
  @{ name = 'job-application-copilot-viewers'; nickname = 'jobappcopilotviewers'; role = 'JobApplicationCopilot.Viewer'; seedUser = $false }
)

$rolesPath = Join-Path $env:TEMP 'jobapp-app-roles.json'
$appRoles | ConvertTo-Json -Depth 10 | Set-Content -Path $rolesPath -Encoding utf8

$existingApps = az ad app list --display-name $AppDisplayName | ConvertFrom-Json
if ($existingApps.Count -gt 0) {
  $appId = $existingApps[0].appId
  az ad app update --id $appId --web-redirect-uris $RedirectUris --enable-id-token-issuance true --sign-in-audience AzureADMyOrg --web-home-page-url $HomePageUrl --app-roles "@$rolesPath" | Out-Null
}
else {
  $created = az ad app create --display-name $AppDisplayName --sign-in-audience AzureADMyOrg --web-redirect-uris $RedirectUris --enable-id-token-issuance true --web-home-page-url $HomePageUrl --app-roles "@$rolesPath" | ConvertFrom-Json
  $appId = $created.appId
}

az ad app update --id $appId --set groupMembershipClaims=SecurityGroup | Out-Null
$app = az ad app show --id $appId | ConvertFrom-Json
$secret = az ad app credential reset --id $appId --append --display-name 'container-apps-auth' --years 2 | ConvertFrom-Json

try {
  $sp = az ad sp show --id $appId | ConvertFrom-Json
}
catch {
  az ad sp create --id $appId | Out-Null
  Start-Sleep -Seconds 15
  $sp = az ad sp show --id $appId | ConvertFrom-Json
}

$graphToken = az account get-access-token --resource-type ms-graph --query accessToken -o tsv
$graphHeaders = @{
  Authorization = "Bearer $graphToken"
  'Content-Type' = 'application/json'
}

$servicePrincipalPatch = @{ appRoleAssignmentRequired = $true } | ConvertTo-Json -Compress
Invoke-RestMethod -Headers $graphHeaders -Method Patch -Uri "https://graph.microsoft.com/v1.0/servicePrincipals/$($sp.id)" -Body $servicePrincipalPatch

$currentUser = az ad signed-in-user show | ConvertFrom-Json
$groups = @()

foreach ($definition in $groupDefinitions) {
  $existingGroup = az ad group list --filter "displayName eq '$($definition.name)'" | ConvertFrom-Json
  if ($existingGroup.Count -gt 0) {
    $group = $existingGroup[0]
  }
  else {
    $group = az ad group create --display-name $definition.name --mail-nickname $definition.nickname --description "Access group for $($definition.role)" | ConvertFrom-Json
  }

  if ($definition.seedUser) {
    try {
      az ad group member add --group $group.id --member-id $currentUser.id | Out-Null
    }
    catch {
    }
  }

  $role = $app.appRoles | Where-Object { $_.value -eq $definition.role }
  $existingAssignments = Invoke-RestMethod -Headers $graphHeaders -Method Get -Uri "https://graph.microsoft.com/v1.0/groups/$($group.id)/appRoleAssignments"
  $alreadyAssigned = $existingAssignments.value | Where-Object { $_.resourceId -eq $sp.id -and $_.appRoleId -eq $role.id }

  if (-not $alreadyAssigned) {
    $body = @{
      principalId = $group.id
      resourceId = $sp.id
      appRoleId = $role.id
    } | ConvertTo-Json -Compress
    Invoke-RestMethod -Headers $graphHeaders -Method Post -Uri "https://graph.microsoft.com/v1.0/groups/$($group.id)/appRoleAssignments" -Body $body | Out-Null
  }

  $groups += [pscustomobject]@{
    name = $definition.name
    id = $group.id
    role = $definition.role
  }
}

[pscustomobject]@{
  tenantId = (az account show --query tenantId -o tsv)
  clientId = $app.appId
  objectId = $app.id
  servicePrincipalObjectId = $sp.id
  clientSecret = $secret.password
  allowedGroupIds = @(
    ($groups | Where-Object role -eq 'JobApplicationCopilot.Admin').id
    ($groups | Where-Object role -eq 'JobApplicationCopilot.Operator').id
  )
  groups = $groups
} | ConvertTo-Json -Depth 10

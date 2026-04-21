targetScope = 'resourceGroup'

@description('Primary Azure region for the deployment.')
param location string = resourceGroup().location

@description('Short lowercase prefix used to derive resource names.')
param baseName string = 'jobappcopilot'

@description('Logical deployment environment name.')
@allowed([
  'test'
  'prod'
])
param deploymentEnvironment string = 'test'

@description('Deploy the Container Apps after the shared infrastructure is ready.')
param deployApps bool = true

@description('Azure Container Registry name.')
param containerRegistryName string = '${baseName}acr'

@description('Container Apps environment name.')
param containerAppsEnvironmentName string = '${baseName}-env'

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string = '${baseName}-logs'

@description('Storage account name for shared generated files.')
param storageAccountName string = '${baseName}files'

@description('Azure Files share name used by the API and MLflow.')
param fileShareName string = 'jobappdata'

@description('Flexible Server name for PostgreSQL.')
param postgresServerName string = '${baseName}-pg'

@description('Administrator username for PostgreSQL Flexible Server.')
param postgresAdminUser string = 'jobappadmin'

@secure()
@description('Administrator password for PostgreSQL Flexible Server.')
param postgresAdminPassword string

@description('PostgreSQL version to deploy.')
param postgresVersion string = '16'

@description('Flexible Server SKU name.')
param postgresSkuName string = 'Standard_B2s'

@description('Flexible Server SKU tier.')
param postgresSkuTier string = 'Burstable'

@description('Application database name.')
param appDatabaseName string = 'jobapp'

@description('MLflow metadata database name.')
param mlflowDatabaseName string = 'mlflow'

@description('Image reference for the shared application image used by the API and MCP.')
param appImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Image reference for the dashboard container.')
param dashboardImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Image reference for the MLflow container.')
param mlflowImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Image reference for the Prometheus container.')
param prometheusImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Image reference for the Grafana container.')
param grafanaImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('LLM provider, copied from the shared environment file or GitHub secrets.')
param llmProvider string = 'openai_compatible'

@description('Base URL for the external LLM endpoint.')
param llmBaseUrl string = 'https://api.cerebras.ai/v1'

@secure()
@description('API key for the external LLM endpoint.')
param llmApiKey string = ''

@description('Model name for the external LLM endpoint.')
param llmModel string = 'llama3.1-8b'

@description('JSON response mode requested from OpenAI-compatible LLM endpoints.')
param llmJsonMode string = 'json_object'

@description('Sampling temperature for the LLM.')
param llmTemperature string = '0.2'

@description('Maximum token budget for generated responses.')
param llmMaxTokens string = '1400'

@description('HTTP timeout in seconds for outbound LLM calls.')
param requestTimeoutSeconds string = '60'

@secure()
@description('Shared token the API uses when calling the tool service.')
param mcpClientAuthToken string = 'change-me-api-token'

@description('Minimum number of replicas for the API app.')
param apiMinReplicas int = 1

@description('Maximum number of replicas for the API app.')
param apiMaxReplicas int = 3

@description('Admin username for Grafana.')
param grafanaAdminUser string = 'admin'

@secure()
@description('Admin password for Grafana.')
param grafanaAdminPassword string = 'ChangeThisGrafanaPassword!'

@description('Optional SMTP host used when email submission is enabled.')
param smtpHost string = ''

@description('Optional SMTP port used when email submission is enabled.')
param smtpPort string = '587'

@description('Optional SMTP user used when email submission is enabled.')
param smtpUser string = ''

@secure()
@description('Optional SMTP password used when email submission is enabled.')
param smtpPassword string = ''

@description('Optional SMTP from address.')
param smtpFrom string = ''

@description('Enable Microsoft Entra protection for external application surfaces.')
param enableEntraProtection bool = false

@description('Tenant ID used by Microsoft Entra sign-in.')
param entraTenantId string = ''

@description('Client ID of the Microsoft Entra application registration used for sign-in.')
param entraClientId string = ''

@secure()
@description('Client secret of the Microsoft Entra application registration used for sign-in.')
param entraClientSecret string = ''

@description('Security group object IDs allowed to access protected external applications.')
param entraAllowedGroupIds array = []

var apiAppName = '${baseName}-api'
var mcpAppName = '${baseName}-mcp'
var dashboardAppName = '${baseName}-dashboard'
var mlflowAppName = '${baseName}-mlflow'
var prometheusAppName = '${baseName}-prometheus'
var grafanaAppName = '${baseName}-grafana'
var sharedStorageName = '${baseName}-sharedfiles'
var apiExternalIngress = !enableEntraProtection
var entraIssuer = empty(entraTenantId) ? '' : 'https://login.microsoftonline.com/${entraTenantId}/v2.0'

var postgresHost = '${postgresServerName}.postgres.database.azure.com'
var appDatabaseUrl = 'postgresql+psycopg://${postgresAdminUser}:${uriComponent(postgresAdminPassword)}@${postgresHost}:5432/${appDatabaseName}?sslmode=require'
var mlflowBackendUri = 'postgresql+psycopg://${postgresAdminUser}:${uriComponent(postgresAdminPassword)}@${postgresHost}:5432/${mlflowDatabaseName}?sslmode=require'

var apiInternalUrl = 'http://${apiAppName}'
var mcpInternalUrl = 'http://${mcpAppName}'
var prometheusInternalUrl = 'http://${prometheusAppName}'
var sharedMountPath = '/mnt/shared'

var dashboardPublicUrl = deployApps ? 'https://${dashboardApp.properties.configuration.ingress.fqdn}' : ''
var apiPublicUrl = deployApps ? 'https://${apiApp.properties.configuration.ingress.fqdn}' : ''
var mlflowPublicUrl = deployApps ? 'https://${mlflowApp.properties.configuration.ingress.fqdn}' : ''
var prometheusPublicUrl = deployApps ? 'https://${prometheusApp.properties.configuration.ingress.fqdn}' : ''
var grafanaPublicUrl = deployApps ? 'https://${grafanaApp.properties.configuration.ingress.fqdn}' : ''
var commonTags = {
  application: 'job-application-copilot'
  environment: deploymentEnvironment
  managedBy: 'codex'
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: commonTags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  tags: commonTags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        days: 14
        status: 'disabled'
      }
      trustPolicy: {
        type: 'Notary'
        status: 'disabled'
      }
    }
  }
}

resource acrPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-acr-pull'
  location: location
  tags: commonTags
}

var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource acrPullIdentityAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, acrPullIdentity.id, 'acrpull')
  scope: containerRegistry
  properties: {
    principalId: acrPullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: commonTags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    largeFileSharesState: 'Enabled'
  }
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  name: '${storageAccount.name}/default/${fileShareName}'
  properties: {
    enabledProtocols: 'SMB'
    shareQuota: 100
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: postgresServerName
  location: location
  tags: commonTags
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    version: postgresVersion
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: 64
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource postgresAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  name: 'AllowAzureServices'
  parent: postgresServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource appDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  name: appDatabaseName
  parent: postgresServer
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource mlflowDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  name: mlflowDatabaseName
  parent: postgresServer
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: commonTags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: listKeys(logAnalytics.id, '2020-08-01').primarySharedKey
      }
    }
  }
}

resource sharedFiles 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  name: sharedStorageName
  parent: containerAppsEnvironment
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: listKeys(storageAccount.id, '2023-05-01').keys[0].value
      accessMode: 'ReadWrite'
      shareName: fileShareName
    }
  }
}

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: apiAppName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullIdentityAssignment
  ]
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: apiExternalIngress
        allowInsecure: false
        targetPort: 8080
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-url'
          value: appDatabaseUrl
        }
        {
          name: 'llm-api-key'
          value: llmApiKey
        }
        {
          name: 'mcp-client-auth-token'
          value: mcpClientAuthToken
        }
        {
          name: 'smtp-password'
          value: empty(smtpPassword) ? 'smtp-not-configured' : smtpPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: appImage
          env: [
            {
              name: 'ENVIRONMENT'
              value: deploymentEnvironment
            }
            {
              name: 'APP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'APP_PORT'
              value: '8080'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'ARTIFACTS_DIR'
              value: '${sharedMountPath}/artifacts'
            }
            {
              name: 'PROFILES_DIR'
              value: '${sharedMountPath}/profiles'
            }
            {
              name: 'REPORTS_DIR'
              value: '${sharedMountPath}/reports'
            }
            {
              name: 'MATCH_THRESHOLD'
              value: '70'
            }
            {
              name: 'ALLOWED_SOURCE_DOMAINS'
              value: 'greenhouse.io,lever.co,workday.com,smartrecruiters.com,linkedin.com,indeed.com'
            }
            {
              name: 'MANUAL_ONLY_DOMAINS'
              value: 'linkedin.com,indeed.com'
            }
            {
              name: 'LLM_PROVIDER'
              value: llmProvider
            }
            {
              name: 'LLM_BASE_URL'
              value: llmBaseUrl
            }
            {
              name: 'LLM_API_KEY'
              secretRef: 'llm-api-key'
            }
            {
              name: 'LLM_MODEL'
              value: llmModel
            }
            {
              name: 'LLM_JSON_MODE'
              value: llmJsonMode
            }
            {
              name: 'LLM_TEMPERATURE'
              value: llmTemperature
            }
            {
              name: 'LLM_MAX_TOKENS'
              value: llmMaxTokens
            }
            {
              name: 'REQUEST_TIMEOUT_SECONDS'
              value: requestTimeoutSeconds
            }
            {
              name: 'MCP_SERVER_URL'
              value: mcpInternalUrl
            }
            {
              name: 'MCP_VERIFY_SSL'
              value: 'true'
            }
            {
              name: 'MCP_CLIENT_SERVICE_NAME'
              value: apiAppName
            }
            {
              name: 'MCP_CLIENT_AUTH_TOKEN'
              secretRef: 'mcp-client-auth-token'
            }
            {
              name: 'DEFAULT_TENANT_ID'
              value: deploymentEnvironment
            }
            {
              name: 'REQUIRE_TENANT_HEADER'
              value: 'false'
            }
            {
              name: 'ALLOWED_TENANTS'
              value: deploymentEnvironment
            }
            {
              name: 'MLFLOW_ENABLED'
              value: 'true'
            }
            {
              name: 'MLFLOW_TRACKING_URI'
              value: 'http://${mlflowAppName}'
            }
            {
              name: 'MLFLOW_EXPERIMENT_NAME'
              value: 'job-application-copilot'
            }
            {
              name: 'MLFLOW_EVAL_EXPERIMENT_NAME'
              value: 'job-application-copilot-evals'
            }
            {
              name: 'SMTP_HOST'
              value: smtpHost
            }
            {
              name: 'SMTP_PORT'
              value: smtpPort
            }
            {
              name: 'SMTP_USER'
              value: smtpUser
            }
            {
              name: 'SMTP_PASSWORD'
              secretRef: 'smtp-password'
            }
            {
              name: 'SMTP_FROM'
              value: smtpFrom
            }
            {
              name: 'COMPANY_SITE_AUTO_OPEN'
              value: 'false'
            }
          ]
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          volumeMounts: [
            {
              volumeName: 'shared-data'
              mountPath: sharedMountPath
            }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
      }
      volumes: [
        {
          name: 'shared-data'
          storageType: 'AzureFile'
          storageName: sharedFiles.name
        }
      ]
    }
  }
}

resource mcpApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: mcpAppName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullIdentityAssignment
  ]
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 8081
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'llm-api-key'
          value: llmApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: appImage
          command: [
            'python'
          ]
          args: [
            '-m'
            'uvicorn'
            'job_app_ops.mcp_app:app'
            '--host'
            '0.0.0.0'
            '--port'
            '8081'
          ]
          env: [
            {
              name: 'ENVIRONMENT'
              value: deploymentEnvironment
            }
            {
              name: 'MCP_PORT'
              value: '8081'
            }
            {
              name: 'ALLOWED_SOURCE_DOMAINS'
              value: 'greenhouse.io,lever.co,workday.com,smartrecruiters.com,linkedin.com,indeed.com'
            }
            {
              name: 'MANUAL_ONLY_DOMAINS'
              value: 'linkedin.com,indeed.com'
            }
            {
              name: 'LLM_PROVIDER'
              value: llmProvider
            }
            {
              name: 'LLM_BASE_URL'
              value: llmBaseUrl
            }
            {
              name: 'LLM_API_KEY'
              secretRef: 'llm-api-key'
            }
            {
              name: 'LLM_MODEL'
              value: llmModel
            }
            {
              name: 'LLM_JSON_MODE'
              value: llmJsonMode
            }
            {
              name: 'LLM_TEMPERATURE'
              value: llmTemperature
            }
            {
              name: 'LLM_MAX_TOKENS'
              value: llmMaxTokens
            }
            {
              name: 'REQUEST_TIMEOUT_SECONDS'
              value: requestTimeoutSeconds
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

resource mlflowApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: mlflowAppName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullIdentityAssignment
  ]
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 5000
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: concat([
        {
          name: 'mlflow-backend-uri'
          value: mlflowBackendUri
        }
      ], enableEntraProtection ? [
        {
          name: 'entra-auth-client-secret'
          value: entraClientSecret
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'mlflow'
          image: mlflowImage
          command: [
            'sh'
          ]
          args: [
            '-c'
            'mlflow server --host 0.0.0.0 --port 5000 --workers 1 --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" --artifacts-destination "$MLFLOW_ARTIFACT_ROOT" --serve-artifacts --allowed-hosts "*" --cors-allowed-origins "*"'
          ]
          env: [
            {
              name: 'MLFLOW_BACKEND_STORE_URI'
              secretRef: 'mlflow-backend-uri'
            }
            {
              name: 'MLFLOW_ARTIFACT_ROOT'
              value: '${sharedMountPath}/mlflow'
            }
          ]
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          volumeMounts: [
            {
              volumeName: 'shared-data'
              mountPath: sharedMountPath
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: [
        {
          name: 'shared-data'
          storageType: 'AzureFile'
          storageName: sharedFiles.name
        }
      ]
    }
  }
}

resource prometheusApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: prometheusAppName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullIdentityAssignment
  ]
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 9090
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: enableEntraProtection ? [
        {
          name: 'entra-auth-client-secret'
          value: entraClientSecret
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: 'prometheus'
          image: prometheusImage
          env: [
            {
              name: 'API_METRICS_TARGET'
              value: apiAppName
            }
            {
              name: 'API_METRICS_SCHEME'
              value: 'http'
            }
            {
              name: 'MCP_METRICS_TARGET'
              value: mcpAppName
            }
            {
              name: 'MCP_METRICS_SCHEME'
              value: 'http'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource grafanaApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: grafanaAppName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullIdentityAssignment
  ]
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 3000
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: concat([
        {
          name: 'grafana-admin-password'
          value: grafanaAdminPassword
        }
      ], enableEntraProtection ? [
        {
          name: 'entra-auth-client-secret'
          value: entraClientSecret
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'grafana'
          image: grafanaImage
          env: [
            {
              name: 'GF_SECURITY_ADMIN_USER'
              value: grafanaAdminUser
            }
            {
              name: 'GF_SECURITY_ADMIN_PASSWORD'
              secretRef: 'grafana-admin-password'
            }
            {
              name: 'PROMETHEUS_URL'
              value: prometheusInternalUrl
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource dashboardApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: dashboardAppName
  location: location
  tags: commonTags
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${acrPullIdentity.id}': {}
    }
  }
  dependsOn: [
    acrPullIdentityAssignment
  ]
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: acrPullIdentity.id
        }
      ]
      secrets: enableEntraProtection ? [
        {
          name: 'entra-auth-client-secret'
          value: entraClientSecret
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: 'dashboard'
          image: dashboardImage
          env: [
            {
              name: 'API_UPSTREAM_URL'
              value: apiInternalUrl
            }
            {
              name: 'TOOL_UPSTREAM_URL'
              value: mcpInternalUrl
            }
            {
              name: 'PUBLIC_GRAFANA_URL'
              value: grafanaPublicUrl
            }
            {
              name: 'PUBLIC_MLFLOW_URL'
              value: mlflowPublicUrl
            }
            {
              name: 'PUBLIC_PROMETHEUS_URL'
              value: prometheusPublicUrl
            }
            {
              name: 'PUBLIC_API_READY_URL'
              value: '/ready'
            }
            {
              name: 'PUBLIC_TOOL_READY_URL'
              value: '/tool-api/ready'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource dashboardAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployApps && enableEntraProtection) {
  parent: dashboardApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
      runtimeVersion: '~1'
    }
    globalValidation: {
      redirectToProvider: 'azureActiveDirectory'
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'entra-auth-client-secret'
          openIdIssuer: entraIssuer
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              groups: entraAllowedGroupIds
            }
          }
          jwtClaimChecks: {
            allowedGroups: entraAllowedGroupIds
          }
        }
      }
    }
  }
}

resource grafanaAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployApps && enableEntraProtection) {
  parent: grafanaApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
      runtimeVersion: '~1'
    }
    globalValidation: {
      redirectToProvider: 'azureActiveDirectory'
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'entra-auth-client-secret'
          openIdIssuer: entraIssuer
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              groups: entraAllowedGroupIds
            }
          }
          jwtClaimChecks: {
            allowedGroups: entraAllowedGroupIds
          }
        }
      }
    }
  }
}

resource mlflowAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployApps && enableEntraProtection) {
  parent: mlflowApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
      runtimeVersion: '~1'
    }
    globalValidation: {
      redirectToProvider: 'azureActiveDirectory'
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'entra-auth-client-secret'
          openIdIssuer: entraIssuer
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              groups: entraAllowedGroupIds
            }
          }
          jwtClaimChecks: {
            allowedGroups: entraAllowedGroupIds
          }
        }
      }
    }
  }
}

resource prometheusAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = if (deployApps && enableEntraProtection) {
  parent: prometheusApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
      runtimeVersion: '~1'
    }
    globalValidation: {
      redirectToProvider: 'azureActiveDirectory'
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          clientSecretSettingName: 'entra-auth-client-secret'
          openIdIssuer: entraIssuer
        }
        validation: {
          allowedAudiences: [
            entraClientId
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              groups: entraAllowedGroupIds
            }
          }
          jwtClaimChecks: {
            allowedGroups: entraAllowedGroupIds
          }
        }
      }
    }
  }
}

output resourceGroupName string = resourceGroup().name
output deploymentEnvironmentName string = deploymentEnvironment
output acrLoginServer string = containerRegistry.properties.loginServer
output postgresHostName string = postgresHost
output dashboardUrl string = dashboardPublicUrl
output apiUrl string = apiPublicUrl
output mlflowUrl string = mlflowPublicUrl
output prometheusUrl string = prometheusPublicUrl
output grafanaUrl string = grafanaPublicUrl
output sharedFilesShare string = fileShare.name

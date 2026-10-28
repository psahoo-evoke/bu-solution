// TransferIQ - Azure infrastructure (resource-group scope).
// Deploy:  az deployment group create -g <rg> -f infra/main.bicep -p infra/main.bicepparam
// See infra/README.md for the two-phase flow (infra first, then the API image).
targetScope = 'resourceGroup'

// ---------- General ----------
@minLength(2)
@maxLength(8)
@description('Environment name, lowercase letters/digits only (used in resource names), e.g. demo, dev.')
param env string = 'demo'

@description('Primary region for most resources.')
param location string = resourceGroup().location

@description('Short prefix for resource names (lowercase letters/digits).')
@maxLength(5)
param namePrefix string = 'tiq'

@description('Extra tags merged into project/env.')
param extraTags object = {}

// ---------- API container ----------
@description('false = phase 1 (everything except the container app). true = also create/update the API container app.')
param deployApi bool = false

@description('Full API image reference, e.g. <acr>.azurecr.io/transferiq-api:<sha>. Required when deployApi = true.')
param apiImage string = ''

@description('Minimum API replicas (1 keeps the demo warm).')
param apiMinReplicas int = 1

@description('TRANSFERIQ_AUTH_MODE. "demo" = X-Demo-Role header (synthetic data only). "entra" currently FAILS CLOSED: the API answers 401 to every route except /api/health, because JWT validation is not built yet (backend/app/guard.py).')
@allowed([ 'demo', 'entra' ])
param authMode string = 'demo'

@description('Extra CORS origins added to TRANSFERIQ_CORS_ORIGINS (the SWA host is always included). Not needed with the SWA linked backend (same origin). "*" is ignored by the API.')
param extraCorsOrigins array = []

// ---------- Static Web App ----------
@description('SWA region (SWA is only offered in a few regions: westus2, centralus, eastus2, westeurope, eastasia).')
param staticWebAppLocation string = 'eastus2'
@allowed([ 'Free', 'Standard' ])
@description('Standard enables the linked /api backend; Free requires the SPA to call the API URL directly.')
param staticWebAppSku string = 'Standard'

// ---------- PostgreSQL ----------
@description('Postgres region (some subscriptions are offer-restricted in some regions; override if the deployment fails with LocationIsOfferRestricted).')
param postgresLocation string = location
param postgresSku string = 'Standard_B1ms'
@description('Object ID of an Entra user/group to be Postgres admin (team access). Empty = none.')
param postgresEntraAdminObjectId string = ''
param postgresEntraAdminName string = ''
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param postgresEntraAdminType string = 'Group'

// ---------- Azure OpenAI ----------
@description('false = no Azure OpenAI; the API uses the offline matcher fallback (ADR 0003).')
param deployOpenAi bool = true
param openAiLocation string = location
param openAiDeploymentName string = 'matcher-chat'
@description('Model name - REQUIRED, no default on purpose. Verify availability: az cognitiveservices model list -l <openAiLocation>.')
param openAiModelName string
@description('Model version - REQUIRED, no default on purpose.')
param openAiModelVersion string
param openAiDeploymentSku string = 'GlobalStandard'
@description('Capacity in 1K tokens/minute.')
param openAiCapacity int = 10
@description('Data-plane API version the API should use.')
param openAiApiVersion string = '2024-10-21'

// ---------- Other services ----------
@allowed([ 'F0', 'S0' ])
param docIntelSku string = 'S0'
@allowed([ 'free', 'basic', 'standard' ])
param searchSku string = 'basic'
param acsDataLocation string = 'United States'

@description('Object ID of a user/group granted Key Vault Secrets Officer (optional).')
param keyVaultAdminObjectId string = ''
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param keyVaultAdminType string = 'Group'

// ---------- Naming ----------
var tags = union({ project: 'transferiq', env: env }, extraTags)
var suffix = substring(uniqueString(resourceGroup().id, env), 0, 6)
var base = '${namePrefix}-${env}'
var compact = toLower('${namePrefix}${env}${suffix}')
var names = {
  law: 'log-${base}'
  appi: 'appi-${base}'
  kv: 'kv-${base}-${suffix}'
  storage: 'st${compact}'
  acr: 'cr${compact}'
  uai: 'id-${base}-api'
  postgres: 'psql-${base}-${suffix}'
  openai: 'oai-${base}-${suffix}'
  docintel: 'di-${base}-${suffix}'
  search: 'srch-${base}-${suffix}'
  acs: 'acs-${base}-${suffix}'
  email: 'ecs-${base}-${suffix}'
  cae: 'cae-${base}'
  api: 'ca-${base}-api'
  swa: 'swa-${base}'
}

// ---------- Foundation ----------
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: { location: location, tags: tags, logAnalyticsName: names.law, appInsightsName: names.appi }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    tags: tags
    name: names.kv
    adminPrincipalId: keyVaultAdminObjectId
    adminPrincipalType: keyVaultAdminType
  }
}

module appiSecret 'modules/kv-secret.bicep' = {
  name: 'kv-appinsights'
  params: {
    vaultName: keyVault.outputs.name
    secretName: 'appinsights-connection-string'
    secretValue: monitoring.outputs.appInsightsConnectionString
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: { location: location, tags: tags, name: names.storage }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    location: location
    tags: tags
    registryName: names.acr
    identityName: names.uai
    keyVaultName: keyVault.outputs.name
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: postgresLocation
    tags: tags
    name: names.postgres
    skuName: postgresSku
    entraAdminObjectId: postgresEntraAdminObjectId
    entraAdminName: postgresEntraAdminName
    entraAdminType: postgresEntraAdminType
  }
}

module ai 'modules/ai.bicep' = {
  name: 'ai'
  params: {
    location: location
    tags: tags
    deployOpenAi: deployOpenAi
    openAiName: names.openai
    openAiLocation: openAiLocation
    openAiDeploymentName: openAiDeploymentName
    openAiModelName: openAiModelName
    openAiModelVersion: openAiModelVersion
    openAiDeploymentSku: openAiDeploymentSku
    openAiCapacity: openAiCapacity
    docIntelName: names.docintel
    docIntelSku: docIntelSku
    searchName: names.search
    searchSku: searchSku
  }
}

module communication 'modules/communication.bicep' = {
  name: 'communication'
  params: {
    tags: tags
    communicationName: names.acs
    emailServiceName: names.email
    keyVaultName: keyVault.outputs.name
    dataLocation: acsDataLocation
  }
}

module staticWebApp 'modules/staticwebapp.bicep' = {
  name: 'staticwebapp'
  params: { location: staticWebAppLocation, tags: tags, name: names.swa, sku: staticWebAppSku }
}

module containerEnv 'modules/containerapps-env.bicep' = {
  name: 'containerapps-env'
  params: { location: location, tags: tags, name: names.cae, logAnalyticsName: monitoring.outputs.logAnalyticsName }
}

// ---------- API (phase 2) ----------
// Env var contract for the backend (documented in infra/README.md). AZURE_OPENAI_ENDPOINT is only
// present when OpenAI is deployed, so the matcher picks the offline fallback otherwise (ADR 0003).
var apiEnvBase = [
  { name: 'TRANSFERIQ_ENV', value: env }
  { name: 'TRANSFERIQ_AUTH_MODE', value: authMode }
  { name: 'TRANSFERIQ_CORS_ORIGINS', value: join(concat([ 'https://${staticWebApp.outputs.defaultHostname}' ], extraCorsOrigins), ',') }
  { name: 'AZURE_KEY_VAULT_URI', value: keyVault.outputs.uri }
  { name: 'AZURE_STORAGE_BLOB_ENDPOINT', value: storage.outputs.blobEndpoint }
  { name: 'AZURE_STORAGE_CONTAINER_TRANSCRIPTS', value: 'transcripts' }
  { name: 'AZURE_STORAGE_CONTAINER_SYLLABI', value: 'syllabi' }
  { name: 'AZURE_SEARCH_ENDPOINT', value: ai.outputs.searchEndpoint }
  { name: 'AZURE_DI_ENDPOINT', value: ai.outputs.docIntelEndpoint }
  { name: 'AZURE_COMMUNICATION_ENDPOINT', value: communication.outputs.endpoint }
  { name: 'ACS_SENDER_ADDRESS', value: communication.outputs.senderAddress }
  { name: 'POSTGRES_HOST', value: postgres.outputs.fqdn }
  { name: 'POSTGRES_DB', value: postgres.outputs.databaseName }
  { name: 'POSTGRES_USER', value: names.api } // Entra principal name of the app's system identity
  { name: 'POSTGRES_AUTH', value: 'entra' } // password = Entra access token for https://ossrdbms-aad.database.windows.net
]
var apiEnvOpenAi = deployOpenAi ? [
  { name: 'AZURE_OPENAI_ENDPOINT', value: ai.outputs.openAiEndpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT', value: ai.outputs.openAiDeploymentName }
  { name: 'AZURE_OPENAI_API_VERSION', value: openAiApiVersion }
] : []

module api 'modules/containerapp-api.bicep' = if (deployApi) {
  name: 'containerapp-api'
  params: {
    location: location
    tags: tags
    name: names.api
    environmentId: containerEnv.outputs.id
    image: apiImage
    registryLoginServer: registry.outputs.loginServer
    pullIdentityId: registry.outputs.identityId
    minReplicas: apiMinReplicas
    envVars: concat(apiEnvBase, apiEnvOpenAi)
    kvSecrets: [
      { name: 'appinsights-cs', keyVaultUrl: appiSecret.outputs.secretUri, envName: 'APPLICATIONINSIGHTS_CONNECTION_STRING' }
      { name: 'acs-cs', keyVaultUrl: communication.outputs.connectionStringSecretUri, envName: 'ACS_CONNECTION_STRING' }
    ]
  }
}

module apiRoles 'modules/roles.bicep' = if (deployApi) {
  name: 'api-roles'
  params: {
    principalId: api!.outputs.principalId
    keyVaultName: keyVault.outputs.name
    storageName: storage.outputs.name
    searchName: ai.outputs.searchName
    docIntelName: ai.outputs.docIntelName
    openAiName: ai.outputs.openAiName
  }
}

module apiPostgresAdmin 'modules/postgres-admin.bicep' = if (deployApi) {
  name: 'api-postgres-admin'
  params: {
    serverName: postgres.outputs.name
    principalId: api!.outputs.principalId
    principalName: names.api
  }
}

module swaBackend 'modules/staticwebapp-backend.bicep' = if (deployApi && staticWebAppSku == 'Standard') {
  name: 'swa-backend-link'
  params: {
    staticWebAppName: staticWebApp.outputs.name
    backendResourceId: api!.outputs.id
    backendLocation: location
  }
}

// ---------- Outputs (no secrets) ----------
output resourceGroupName string = resourceGroup().name
output acrName string = registry.outputs.registryName
output acrLoginServer string = registry.outputs.loginServer
output containerAppName string = names.api
output apiUrl string = deployApi ? api!.outputs.url : ''
output staticWebAppName string = staticWebApp.outputs.name
output staticWebAppUrl string = 'https://${staticWebApp.outputs.defaultHostname}'
output keyVaultName string = keyVault.outputs.name
output storageAccountName string = storage.outputs.name
output postgresHost string = postgres.outputs.fqdn
output searchEndpoint string = ai.outputs.searchEndpoint
output docIntelEndpoint string = ai.outputs.docIntelEndpoint
output openAiEndpoint string = ai.outputs.openAiEndpoint

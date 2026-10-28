using './main.bicep'

// ---- Fill these in before the first deploy (see infra/README.md) ----
param env = 'demo'
param location = 'eastus2'
param staticWebAppLocation = 'eastus2'

// Azure OpenAI model: VERIFY before deploying - model names/versions/SKUs change and differ by region:
//   az cognitiveservices model list -l <openAiLocation> --query "[?model.name=='<name>'].{v:model.version,skus:model.skus[].name}" -o table
// The values below are placeholders the team must confirm; set deployOpenAi = false to run with the offline matcher.
param deployOpenAi = true
param openAiLocation = 'eastus2'
param openAiModelName = 'gpt-4o-mini'
param openAiModelVersion = '2024-07-18'
param openAiDeploymentSku = 'GlobalStandard'
param openAiCapacity = 10

// Optional: Entra group for humans (Postgres admin, Key Vault secrets officer). Leave empty to skip.
param postgresEntraAdminObjectId = ''
param postgresEntraAdminName = ''
param keyVaultAdminObjectId = ''

// Phase 1 = false. deploy.yml overrides deployApi/apiImage on the command line for phase 2.
param deployApi = false
param apiImage = ''
param authMode = 'demo'
param extraCorsOrigins = []

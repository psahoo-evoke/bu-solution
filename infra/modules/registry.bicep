// Azure Container Registry (admin user disabled) + a user-assigned identity used by the
// container app for image pull and Key Vault secret references.
// Why a user-assigned identity here: its roles exist BEFORE the container app is created, so the
// first revision can pull from ACR and resolve Key Vault references without a race. The API's own
// data-plane access (OpenAI, Search, Storage, ...) uses the app's system-assigned identity (roles.bicep).
param location string
param tags object
param registryName string
param identityName string
param keyVaultName string
@allowed([ 'Basic', 'Standard', 'Premium' ])
param sku string = 'Basic'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: { name: sku }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource uai 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var kvSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

resource pullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uai.id, acrPull)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
    principalId: uai.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, uai.id, kvSecretsUser)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
    principalId: uai.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output registryId string = acr.id
output registryName string = acr.name
output loginServer string = acr.properties.loginServer
output identityId string = uai.id
output identityClientId string = uai.properties.clientId
output identityPrincipalId string = uai.properties.principalId

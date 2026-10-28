// Data-plane role assignments for the API's system-assigned managed identity (least privilege per service).
param principalId string
param keyVaultName string
param storageName string
param searchName string
param docIntelName string
param openAiName string = ''

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: keyVaultName }
resource sa 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageName }
resource search 'Microsoft.Search/searchServices@2023-11-01' existing = { name: searchName }
resource docintel 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = { name: docIntelName }
resource oai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!empty(openAiName)) {
  name: empty(openAiName) ? 'unused' : openAiName
}

var roles = {
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  blobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // create/update the BU course index
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
}

resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, principalId, roles.kvSecretsUser)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sa.id, principalId, roles.blobDataContributor)
  scope: sa
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobDataContributor)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource searchDataRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, principalId, roles.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource searchSvcRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, principalId, roles.searchServiceContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource docRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(docintel.id, principalId, roles.cognitiveServicesUser)
  scope: docintel
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesUser)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource oaiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(openAiName)) {
  name: guid(oai.id, principalId, roles.openAiUser)
  scope: oai
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// Azure OpenAI (+ one chat model deployment), Document Intelligence and Azure AI Search.
// All three have local (key) auth disabled: the API authenticates with its managed identity.
param location string
param tags object

@description('Deploy Azure OpenAI. false = the API runs the offline matcher fallback (ADR 0003).')
param deployOpenAi bool = true
param openAiName string
@description('Azure OpenAI region (model availability differs by region).')
param openAiLocation string = location
@description('Model deployment name the API calls (AZURE_OPENAI_DEPLOYMENT).')
param openAiDeploymentName string
@description('Model name, e.g. a GPT-4o-class chat model. MUST exist in openAiLocation for the chosen SKU - check with: az cognitiveservices model list -l <region>.')
param openAiModelName string
@description('Model version for openAiModelName (from the same az command).')
param openAiModelVersion string
@description('Deployment SKU: GlobalStandard, Standard, DataZoneStandard, ...')
param openAiDeploymentSku string = 'GlobalStandard'
@description('Capacity in units of 1,000 tokens per minute.')
param openAiCapacity int = 10

param docIntelName string
@allowed([ 'F0', 'S0' ])
@description('F0 is free but only one per subscription and limited to 2 pages per document.')
param docIntelSku string = 'S0'

param searchName string
@allowed([ 'free', 'basic', 'standard' ])
param searchSku string = 'basic'

resource oai 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (deployOpenAi) {
  name: openAiName
  location: openAiLocation
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: openAiName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource oaiDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployOpenAi) {
  parent: oai
  name: openAiDeploymentName
  sku: { name: openAiDeploymentSku, capacity: openAiCapacity }
  properties: {
    model: { format: 'OpenAI', name: openAiModelName, version: openAiModelVersion }
    versionUpgradeOption: 'NoAutoUpgrade' // keep the evaluated model fixed (quality gates)
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource docintel 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: docIntelName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: { name: docIntelSku }
  properties: {
    customSubDomainName: docIntelName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchName
  location: location
  tags: tags
  sku: { name: searchSku }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: true
  }
}

output openAiId string = deployOpenAi ? oai!.id : ''
output openAiName string = deployOpenAi ? oai!.name : ''
output openAiEndpoint string = deployOpenAi ? oai!.properties.endpoint : ''
output openAiDeploymentName string = deployOpenAi ? oaiDeployment!.name : ''
output docIntelId string = docintel.id
output docIntelName string = docintel.name
output docIntelEndpoint string = docintel.properties.endpoint
output searchId string = search.id
output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'

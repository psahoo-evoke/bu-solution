// Key Vault in RBAC mode (no access policies). Secrets are read by the API through managed identity.
param location string
param tags object
param name string
@description('Object ID of a human/group to grant Key Vault Secrets Officer (optional, for break-glass inspection). Empty = none.')
param adminPrincipalId string = ''
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param adminPrincipalType string = 'Group'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // Purge protection left off so a hackathon resource group can be torn down and recreated.
    // Turn it on (enablePurgeProtection: true) for any non-demo environment.
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

var kvSecretsOfficer = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
resource adminRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminPrincipalId)) {
  name: guid(kv.id, adminPrincipalId, kvSecretsOfficer)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsOfficer)
    principalId: adminPrincipalId
    principalType: adminPrincipalType
  }
}

output id string = kv.id
output name string = kv.name
output uri string = kv.properties.vaultUri

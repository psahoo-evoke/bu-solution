// Azure Communication Services + Email with an Azure-managed sender domain (reminders day 7/21/45).
// The ACS connection string is written straight into Key Vault; it never appears in outputs or workflows.
param tags object
param communicationName string
param emailServiceName string
param keyVaultName string
@description('ACS data residency, e.g. "United States", "Europe".')
param dataLocation string = 'United States'

resource email 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: emailServiceName
  location: 'global'
  tags: tags
  properties: { dataLocation: dataLocation }
}

resource domain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: email
  name: 'AzureManagedDomain'
  location: 'global'
  tags: tags
  properties: {
    domainManagement: 'AzureManaged'
    userEngagementTracking: 'Disabled'
  }
}

resource acs 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: communicationName
  location: 'global'
  tags: tags
  properties: {
    dataLocation: dataLocation
    linkedDomains: [ domain.id ]
  }
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource acsSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'acs-connection-string'
  properties: {
    value: acs.listKeys().primaryConnectionString
    contentType: 'text/plain'
  }
}

output communicationName string = acs.name
output endpoint string = 'https://${acs.properties.hostName}'
output senderAddress string = 'DoNotReply@${domain.properties.mailFromSenderDomain}'
output connectionStringSecretUri string = acsSecret.properties.secretUri

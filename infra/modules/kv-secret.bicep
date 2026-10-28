// Writes one secret into an existing Key Vault and returns its version-less URI
// (Container Apps Key Vault references always resolve the latest version).
param vaultName string
param secretName string
@secure()
param secretValue string

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}

resource secret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: secretName
  properties: {
    value: secretValue
    contentType: 'text/plain'
  }
}

output secretUri string = secret.properties.secretUri

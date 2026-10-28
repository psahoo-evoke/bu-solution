// Makes the API's system-assigned managed identity an Entra administrator of the Postgres server.
// Demo simplification: a production setup would create a least-privilege role with
// pgaadauth_create_principal() and GRANT only the tables the API needs.
param serverName string
param principalId string
@description('For a managed identity the principal name is the resource name (the container app name).')
param principalName string

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: serverName
}

resource apiAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: pg
  name: principalId
  properties: {
    principalType: 'ServicePrincipal'
    principalName: principalName
    tenantId: subscription().tenantId
  }
}

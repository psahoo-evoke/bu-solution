// PostgreSQL Flexible Server, Entra ID authentication only (no password auth), small burstable SKU.
param location string
param tags object
param name string
param databaseName string = 'transferiq'
param version string = '16'
param skuName string = 'Standard_B1ms'
param storageSizeGB int = 32

@description('Entra admin for humans (object ID of a user or group). Empty = only the API identity is admin (added later by postgres-admin.bicep).')
param entraAdminObjectId string = ''
@description('Display name (UPN or group name) of the Entra admin above.')
param entraAdminName string = ''
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param entraAdminType string = 'Group'

@description('Demo shortcut: allow connections from any Azure service (Container Apps without VNet has no fixed egress IP). Replace with VNet integration + private endpoint for production.')
param allowAzureServices bool = true

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: skuName, tier: 'Burstable' }
  properties: {
    version: version
    storage: { storageSizeGB: storageSizeGB, autoGrow: 'Disabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: subscription().tenantId
    }
    network: { publicNetworkAccess: 'Enabled' }
  }
}

resource db 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: databaseName
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource fwAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (allowAzureServices) {
  parent: pg
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
  dependsOn: [ db ]
}

// Server-level operations must not overlap, so the admin is added after the DB + firewall rule.
resource humanAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = if (!empty(entraAdminObjectId)) {
  parent: pg
  name: empty(entraAdminObjectId) ? 'none' : entraAdminObjectId
  properties: {
    principalType: entraAdminType
    principalName: entraAdminName
    tenantId: subscription().tenantId
  }
  dependsOn: [ db, fwAzure ]
}

output id string = pg.id
output name string = pg.name
output fqdn string = pg.properties.fullyQualifiedDomainName
output databaseName string = db.name

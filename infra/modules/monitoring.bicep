// Log Analytics workspace + workspace-based Application Insights.
param location string
param tags object
param logAnalyticsName string
param appInsightsName string
@description('Days to keep logs. 30 is the free-retention floor.')
param retentionInDays int = 30

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionInDays
    workspaceCapping: { dailyQuotaGb: 1 } // hackathon cost guard
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    IngestionMode: 'LogAnalytics'
    DisableLocalAuth: false // connection-string ingestion; switch to Entra ingestion for production
  }
}

output logAnalyticsId string = law.id
output logAnalyticsName string = law.name
output logAnalyticsCustomerId string = law.properties.customerId
output appInsightsName string = appi.name
output appInsightsConnectionString string = appi.properties.ConnectionString

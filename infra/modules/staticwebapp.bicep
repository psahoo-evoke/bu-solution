// Static Web App for the Angular SPA. Content is pushed by deploy.yml (no GitHub repo link here,
// so the deployment token is fetched at deploy time via OIDC instead of living in repo secrets).
param location string
param tags object
param name string
@allowed([ 'Free', 'Standard' ])
@description('Standard is required for the linked /api backend.')
param sku string = 'Standard'

resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  sku: { name: sku, tier: sku }
  properties: {
    stagingEnvironmentPolicy: 'Disabled'
    allowConfigFileUpdates: true
    enterpriseGradeCdnStatus: 'Disabled'
  }
}

output id string = swa.id
output name string = swa.name
output defaultHostname string = swa.properties.defaultHostname

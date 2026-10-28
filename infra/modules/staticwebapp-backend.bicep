// Links the container app as the SWA backend: the SPA calls relative /api/* and SWA proxies it.
// Requires the Standard SWA plan.
param staticWebAppName string
param backendResourceId string
param backendLocation string

resource swa 'Microsoft.Web/staticSites@2023-12-01' existing = {
  name: staticWebAppName
}

resource link 'Microsoft.Web/staticSites/linkedBackends@2023-12-01' = {
  parent: swa
  name: 'api'
  properties: {
    backendResourceId: backendResourceId
    region: backendLocation
  }
}

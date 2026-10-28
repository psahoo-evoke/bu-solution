// The FastAPI container app. Identities:
//  - system-assigned: data-plane access (OpenAI, Search, Doc Intelligence, Storage, Key Vault, Postgres)
//  - user-assigned (registry.bicep): ACR pull + Key Vault secret references at revision start
// DefaultAzureCredential in the app picks the SYSTEM-assigned identity because AZURE_CLIENT_ID is not set.
// Do not add AZURE_CLIENT_ID (it would switch the app to the user-assigned identity, which has no data roles).
param location string
param tags object
param name string
param environmentId string
param image string
param targetPort int = 8000
param registryLoginServer string
param pullIdentityId string
param minReplicas int = 1
param maxReplicas int = 2
param cpu string = '0.5'
param memory string = '1Gi'
@description('Plain (non-secret) environment variables: [{ name, value }].')
param envVars array
@description('Key Vault-backed secrets: [{ name, keyVaultUrl, envName }]. Resolved with the user-assigned identity.')
param kvSecrets array = []

var secretEnv = [for s in kvSecrets: { name: s.envName, secretRef: s.name }]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'SystemAssigned,UserAssigned'
    userAssignedIdentities: { '${pullIdentityId}': {} }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
        // No ingress corsPolicy on purpose: the API owns CORS (TRANSFERIQ_CORS_ORIGINS, CORSMiddleware).
        // Two CORS layers can emit conflicting/duplicate Access-Control-* headers (devops-02).
      }
      registries: [
        { server: registryLoginServer, identity: pullIdentityId }
      ]
      secrets: [for s in kvSecrets: {
        name: s.name
        keyVaultUrl: s.keyVaultUrl
        identity: pullIdentityId
      }]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          resources: { cpu: json(cpu), memory: memory }
          env: concat(envVars, secretEnv)
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/api/health', port: targetPort }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/api/health', port: targetPort }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas // 1 = no cold start during the demo
        maxReplicas: maxReplicas
        rules: [ { name: 'http', http: { metadata: { concurrentRequests: '50' } } } ]
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output url string = 'https://${app.properties.configuration.ingress.fqdn}'
output principalId string = app.identity.principalId

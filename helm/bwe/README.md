# BWE Helm Chart

Helm chart for deploying the Bird Watchers' Emporium FastAPI LangGraph application.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- Docker image built from `src/app/Dockerfile`

## Building the Docker Image

Before deploying, build and push your Docker image:

```bash
# From the repository root
docker build -f src/app/Dockerfile -t bwe-api:latest .

# Tag and push to your registry (example)
docker tag bwe-api:latest your-registry/bwe-api:latest
docker push your-registry/bwe-api:latest
```

## Installing the Chart

To install the chart with the release name `bwe`:

```bash
helm install bwe ./helm/bwe
```

To install with custom values:

```bash
helm install bwe ./helm/bwe -f my-values.yaml
```

## Uninstalling the Chart

To uninstall/delete the `bwe` deployment:

```bash
helm uninstall bwe
```

## Configuration

The following table lists the configurable parameters and their default values:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Docker image repository | `bwe-api` |
| `image.tag` | Docker image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `service.type` | Kubernetes service type | `ClusterIP` |
| `service.port` | Service port | `80` |
| `service.targetPort` | Container port | `8000` |
| `env.APP_ENV` | Application environment | `production` |
| `env.API_PORT` | API port | `8000` |
| `env.LOG_LEVEL` | Log level | `INFO` |
| `ingress.enabled` | Enable ingress | `false` |
| `autoscaling.enabled` | Enable HPA | `false` |
| `resources` | Resource limits/requests | `{}` |

## Accessing the Service

### ClusterIP (default)

The service is accessible within the cluster at:

```
http://bwe:80
```

Or using the full service name:

```
http://bwe.default.svc.cluster.local:80
```

### NodePort

To expose via NodePort, set in `values.yaml`:

```yaml
service:
  type: NodePort
  nodePort: 30080
```

Then access at:

```
http://<node-ip>:30080
```

### Ingress

To enable ingress, set in `values.yaml`:

```yaml
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: bwe.example.com
      paths:
        - path: /
          pathType: Prefix
```

## Testing

After deployment, test the health endpoint:

```bash
# Port-forward to access locally
kubectl port-forward svc/bwe 8080:80

# Test health endpoint
curl http://localhost:8080/health

# Test query endpoint
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is 2+2?"}'
```

## Llama Server Deployment

The chart includes an optional llama-server deployment for running Qwen-3-VL models.

### Prerequisites

1. **Model Files**: Ensure these files exist:
   - `Qwen3VL-30B-A3B-Thinking-Q8_0.gguf` (main model file)
   - `mmproj-Qwen3VL-30B-A3B-Thinking-Q8_0.gguf` (vision projection layer)

2. **Storage Setup**: Choose one of the storage options below based on your setup.

3. **User/Group Permissions**: Configure the UID/GID in `values.yaml` to match the owner of the model files:

```yaml
llamaServer:
  user:
    userId: 1000   # UID of user that owns the model files
    groupId: 1000  # GID of group that owns the model files
```

### Storage Options

The chart supports three storage types for accessing your models:

#### Option 1: PersistentVolumeClaim (PVC) - Recommended

Use this if you have a storage class configured (e.g., NFS, Ceph, or a cloud provider's storage).

```yaml
llamaServer:
  storage:
    type: "pvc"
    size: "100Gi"
    storageClassName: ""  # Use default, or specify your storage class
    readOnly: true
```

**To use an existing PVC:**
1. Create a PVC manually that points to your storage
2. Update `values.yaml`:
   ```yaml
   llamaServer:
     storage:
       type: "pvc"
       storageClassName: "your-storage-class"
   ```

#### Option 2: Local PersistentVolume

Use this if `/data/models` exists on a specific Kubernetes node and you want Kubernetes to manage it as a PV.

```yaml
llamaServer:
  storage:
    type: "local"
    createPV: true
    localPath: /data/models
    nodeName: "your-node-name"  # Node where /data/models exists
    size: "100Gi"
    storageClassName: "local-storage"
    readOnly: true
```

**Setup steps:**
1. Ensure `/data/models` exists on the specified node
2. Set `nodeName` to match your node's hostname
3. The chart will create a Local PV that binds to that node

#### Option 3: HostPath (Direct Mount)

Use this only if you're running a single-node cluster (like minikube/k3s) and `/data/models` exists on that node.

```yaml
llamaServer:
  storage:
    type: "hostPath"
    hostPath: /data/models
    readOnly: true
```

**Important:** This requires `/data/models` to exist on the Kubernetes node, not just your local machine. If your node is your local machine, ensure the path is accessible.

### Setting Up Storage for Your Local `/data` Drive

If `/data` is on your local machine and you're running Kubernetes locally:

1. **For single-node clusters (k3s, minikube, kind):**
   - Mount your `/data` drive to the node (if using Docker Desktop, use bind mounts)
   - Use `hostPath` storage type

2. **For multi-node or production:**
   - Set up NFS or another network storage solution
   - Export `/data/models` via NFS
   - Use PVC with an NFS storage class
   - Or use a cloud storage solution (S3, GCS, etc.) and sync models to a PVC

3. **Quick setup with Local PV (if node has /data):**
   ```yaml
   llamaServer:
     storage:
       type: "local"
       createPV: true
       localPath: /data/models
       nodeName: "your-node-hostname"  # Get with: kubectl get nodes
       size: "100Gi"
       storageClassName: "local-storage"
   ```

### Enabling Llama Server

Set `llamaServer.enabled: true` in `values.yaml` (default is `true`).

### Configuration

Key configuration options in `values.yaml`:

```yaml
llamaServer:
  enabled: true
  replicaCount: 1
  
  image:
    repository: llama-server  # Your llama-server image
    tag: "latest"
  
  user:
    userId: 1000   # Must match owner of model files
    groupId: 1000  # Must match group of model files
  
  storage:
    type: "pvc"  # or "hostPath" or "local"
    size: "100Gi"
    storageClassName: ""  # Use default or specify
  
  modelPath: /data/models/Qwen3VL-30B-A3B-Thinking-Q8_0.gguf
  mmprojPath: /data/models/mmproj-Qwen3VL-30B-A3B-Thinking-Q8_0.gguf
  
  port: 8080
  
  resources:
    requests:
      cpu: "2"
      memory: "8Gi"
    limits:
      cpu: "8"
      memory: "32Gi"
```

### Accessing Llama Server

The llama-server service is accessible within the cluster at:

```
http://bwe-llama-server:8080
```

Or using the full service name:

```
http://bwe-llama-server.default.svc.cluster.local:8080
```

### Node Selection

If your models are only on specific nodes (especially with Local PV), use node selectors:

```yaml
llamaServer:
  nodeSelector:
    kubernetes.io/hostname: model-node-1
```

Or use affinity rules to prefer nodes with models:

```yaml
llamaServer:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          preference:
            matchExpressions:
              - key: model-storage
                operator: In
                values:
                  - available
```

**Note:** If using Local PV (`storage.type: "local"`), the PV will automatically bind to the specified node, so node selection is handled automatically.

### Security Notes

- The deployment runs as a non-root user (specified by `userId`/`groupId`)
- The models volume is mounted read-only by default (configurable via `storage.readOnly`)
- The pod's `fsGroup` is set to match the group ID for proper file access
- For hostPath/Local PV: Ensure the path exists on the node and has correct permissions before deployment
- For PVC: Ensure the underlying storage has appropriate access controls

## Notes

- The FastAPI deployment uses the `/health` endpoint for liveness and readiness probes
- Default container port is 8000 (matching `API_PORT` env var)
- Service exposes on port 80, targeting container port 8000
- Environment variables can be overridden in `values.yaml`
- Llama-server health checks use `/health` endpoint (or TCP socket check as fallback)


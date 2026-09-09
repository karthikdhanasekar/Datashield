# DataShield OSINT - Kubernetes Deployment Guide

## Prerequisites

1. **Kubernetes Cluster** (v1.24+)
   - Managed: GKE, EKS, AKS, or DigitalOcean Kubernetes
   - Self-hosted: kubeadm, k3s, microk8s

2. **kubectl** installed and configured

3. **Helm 3** (for cert-manager and ingress-nginx)

4. **Container Registry** access (GitHub Container Registry, Docker Hub, etc.)

---

## Quick Start

### 1. Install Prerequisites

```bash
# Install cert-manager (for SSL certificates)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Install ingress-nginx controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Verify installations
kubectl get pods -n cert-manager
kubectl get pods -n ingress-nginx
```

### 2. Configure Secrets

```bash
# Copy and edit secrets
cp secrets.yaml secrets-prod.yaml

# IMPORTANT: Update all secret values in secrets-prod.yaml
# Never commit secrets-prod.yaml to git!
```

### 3. Update Configuration

Edit `configmap.yaml` and `ingress.yaml` with your domain names:
- Replace `yourdomain.com` with your actual domain
- Update `cert-manager-issuer.yaml` with your email

### 4. Build and Push Docker Images

```bash
# Build images
docker build -t ghcr.io/your-org/datashield-backend:latest backend/
docker build -t ghcr.io/your-org/datashield-frontend:latest frontend/

# Push to registry
docker push ghcr.io/your-org/datashield-backend:latest
docker push ghcr.io/your-org/datashield-frontend:latest
```

### 5. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Apply all manifests
kubectl apply -f configmap.yaml
kubectl apply -f secrets-prod.yaml
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f redis-statefulset.yaml
kubectl apply -f elasticsearch-statefulset.yaml
kubectl apply -f minio-statefulset.yaml

# Wait for stateful services to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n datashield --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n datashield --timeout=300s

# Deploy application
kubectl apply -f backend-deployment.yaml
kubectl apply -f frontend-deployment.yaml

# Setup networking
kubectl apply -f cert-manager-issuer.yaml
kubectl apply -f ingress.yaml
kubectl apply -f network-policies.yaml

# High availability
kubectl apply -f pod-disruption-budget.yaml
kubectl apply -f resource-quotas.yaml

# Monitoring
kubectl apply -f service-monitor.yaml
```

### 6. Or Use Kustomize (Recommended)

```bash
# Deploy everything at once
kubectl apply -k .

# Check deployment status
kubectl get all -n datashield
```

---

## Post-Deployment Steps

### 1. Run Database Migrations

```bash
# Get backend pod name
kubectl get pods -n datashield | grep backend

# Run migrations
kubectl exec -it datashield-backend-xxxx -n datashield -- \
  alembic upgrade head
```

### 2. Create Admin User

```bash
kubectl exec -it datashield-backend-xxxx -n datashield -- \
  python scripts/create_admin.py
```

### 3. Verify SSL Certificate

```bash
# Check certificate status
kubectl describe certificate datashield-tls-cert -n datashield

# Get ingress IP
kubectl get ingress -n datashield
```

### 4. DNS Configuration

Point your domain to the ingress controller's external IP:

```bash
# Get the external IP
kubectl get svc -n ingress-nginx

# Add DNS records:
# A record: yourdomain.com → EXTERNAL_IP
# A record: www.yourdomain.com → EXTERNAL_IP
# A record: api.yourdomain.com → EXTERNAL_IP
```

---

## Scaling

### Manual Scaling

```bash
# Scale backend
kubectl scale deployment datashield-backend --replicas=5 -n datashield

# Scale celery workers
kubectl scale deployment datashield-celery-worker --replicas=10 -n datashield

# Scale frontend
kubectl scale deployment datashield-frontend --replicas=4 -n datashield
```

### Auto-Scaling

HPA (Horizontal Pod Autoscaler) is already configured:
- Backend: 3-10 replicas (CPU: 70%, Memory: 80%)
- Celery Workers: 3-15 replicas (CPU: 75%, Memory: 85%)
- Frontend: 2-8 replicas (CPU: 70%, Memory: 80%)

```bash
# Check HPA status
kubectl get hpa -n datashield
```

---

## Monitoring

### View Logs

```bash
# Backend logs
kubectl logs -f deployment/datashield-backend -n datashield

# Celery worker logs
kubectl logs -f deployment/datashield-celery-worker -n datashield

# All pod logs
kubectl logs -f -l app.kubernetes.io/part-of=datashield -n datashield --max-log-requests=10
```

### Check Pod Status

```bash
kubectl get pods -n datashield -w
```

### View Metrics

```bash
kubectl top pods -n datashield
kubectl top nodes
```

---

## Backup & Disaster Recovery

### Postgres Backup

```bash
# Create backup
kubectl exec -it postgres-0 -n datashield -- \
  pg_dump -U datashield datashield > backup-$(date +%Y%m%d).sql

# Restore backup
kubectl exec -i postgres-0 -n datashield -- \
  psql -U datashield datashield < backup-20240101.sql
```

### Persistent Volume Snapshots

```bash
# List persistent volumes
kubectl get pv

# Create volume snapshot (if supported by storage class)
kubectl create -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: postgres-snapshot-$(date +%Y%m%d)
  namespace: datashield
spec:
  volumeSnapshotClassName: standard
  source:
    persistentVolumeClaimName: postgres-storage-postgres-0
EOF
```

---

## Rolling Updates

```bash
# Update backend image
kubectl set image deployment/datashield-backend \
  backend=ghcr.io/your-org/datashield-backend:v1.1.0 \
  -n datashield

# Watch rollout status
kubectl rollout status deployment/datashield-backend -n datashield

# Rollback if needed
kubectl rollout undo deployment/datashield-backend -n datashield
```

---

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod
kubectl describe pod datashield-backend-xxxx -n datashield

# Check events
kubectl get events -n datashield --sort-by='.lastTimestamp'

# Check logs
kubectl logs datashield-backend-xxxx -n datashield --previous
```

### Connection Issues

```bash
# Test database connection
kubectl run -it --rm debug --image=postgres:15-alpine --restart=Never -n datashield -- \
  psql -h postgres-service -U datashield -d datashield

# Test redis connection
kubectl run -it --rm debug --image=redis:7-alpine --restart=Never -n datashield -- \
  redis-cli -h redis-service ping
```

### Network Policy Issues

```bash
# Temporarily disable network policies
kubectl delete networkpolicies --all -n datashield

# Re-enable after testing
kubectl apply -f network-policies.yaml
```

---

## Security Best Practices

1. **Secrets Management**
   - Use external secrets operator or sealed secrets
   - Never commit secrets to git
   - Rotate secrets regularly

2. **Network Policies**
   - Keep network policies enabled
   - Only allow necessary traffic
   - Regular security audits

3. **RBAC**
   - Principle of least privilege
   - Separate service accounts per component
   - Regular access reviews

4. **Image Security**
   - Scan images for vulnerabilities
   - Use minimal base images
   - Keep images updated

5. **TLS Everywhere**
   - Enforce HTTPS
   - Use cert-manager for certificate management
   - Enable mTLS for service-to-service communication

---

## Resource Requirements

### Minimum Cluster Size

- **Nodes**: 3 (for high availability)
- **CPU**: 16 cores total
- **Memory**: 32 GB total
- **Storage**: 200 GB SSD

### Recommended Production Size

- **Nodes**: 5-10
- **CPU**: 32-64 cores total
- **Memory**: 64-128 GB total
- **Storage**: 500 GB - 1 TB SSD

---

## Cost Optimization

1. Use node auto-scaling
2. Enable cluster autoscaler
3. Use spot/preemptible instances for dev/test
4. Set appropriate resource requests/limits
5. Use PodDisruptionBudgets for safe scaling

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/datashield-osint/issues
- Documentation: https://docs.datashield.com
- Email: support@datashield.com

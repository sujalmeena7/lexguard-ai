# LexGuard AI — AWS EC2 Deployment Guide (ap-south-1)

Cost-optimized deployment using a single EC2 instance with Docker containers.

## Architecture

| Component | Choice | Monthly Cost |
|-----------|--------|-------------|
| Compute | EC2 t3.medium (2 vCPU, 4GB) | ~$30 |
| Database | MongoDB 7 Docker sidecar | $0 |
| Storage | 20GB GP3 EBS (root) | ~$1.60 |
| Load Balancer | **None** — Elastic IP only | $0 |
| SSL | **None** — HTTP only (add Caddy later) | $0 |
| **Total** | | **~$32/mo** |

With $200 AWS credits, this runs for **~6 months free**.

> **Note:** t3.medium has 4GB RAM. MongoDB cache is capped to 1GB in `docker-compose.yml` to leave headroom for the backend. Monitor with `docker stats` under load.

## Important: Database Choice

Your backend code uses **MongoDB** (via `motor`/`pymongo`), not PostgreSQL. The `docker-compose.yml` runs MongoDB 7 as a Docker sidecar. If you want to migrate to PostgreSQL in the future, the code would need significant refactoring.

## Prerequisites

1. AWS account with $200 credits
2. A domain name (optional, but recommended for SSL)
3. Your `.env` file with real API keys

## Step-by-Step Deployment

### 1. Launch EC2 Instance

- **Region**: `ap-south-1` (Mumbai)
- **AMI**: Ubuntu 22.04 LTS (HVM, SSD)
- **Instance type**: `t3.medium`
- **Storage**: 20GB GP3 (default IOPS, delete on termination)
- **Security Group**:
  - SSH (22) — your IP only
  - HTTP (80) — 0.0.0.0/0 (optional, for Caddy)
  - HTTPS (443) — 0.0.0.0/0 (optional, for Caddy)
  - Custom TCP (8000) — 0.0.0.0/0 (backend API)
- **Key pair**: Create or use existing `.pem`

### 2. Allocate & Associate Elastic IP

```bash
aws ec2 allocate-address --region ap-south-1
aws ec2 associate-address --instance-id i-xxxxxxxx --allocation-id eipalloc-xxxxxxxx
```

### 3. Copy .env and Setup Script

```bash
# From your local machine:
scp -i key.pem backend/.env ubuntu@<ELASTIC_IP>:/home/ubuntu/
scp -i key.pem scripts/setup_ec2.sh ubuntu@<ELASTIC_IP>:/home/ubuntu/
```

### 4. Run Setup Script

```bash
ssh -i key.pem ubuntu@<ELASTIC_IP>
chmod +x setup_ec2.sh
sudo ./setup_ec2.sh
```

The script will:
- Update Ubuntu and install Docker
- Clone the repository
- Build and start the containers
- Configure UFW firewall
- Enable auto-restart on boot

### 5. Verify Deployment

```bash
# On the EC2 instance:
curl http://localhost:8000/
# Expected: {"service": "LexGuard AI", "status": "ok", "version": "1.0.0"}

# Check container logs
docker compose logs -f backend
docker compose logs -f mongodb
```

### 6. Update Frontend CORS

In your Vercel/frontend environment, update:
- `CORS_ORIGINS` in the EC2 `.env` to include your Vercel URL
- Restart: `docker compose restart backend`

### 7. (Optional) Enable HTTPS with Caddy

```bash
# Edit backend/Caddyfile — replace api.yourdomain.com with your domain
# Uncomment the caddy service in docker-compose.yml
cd /opt/lexguard/backend
docker compose up -d caddy
```

## Useful Commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f mongodb

# Restart services
docker compose restart backend

# Update after code changes
cd /opt/lexguard && git pull origin main
cd backend && docker compose up -d --build

# Check resource usage
docker stats

# SSH tunnel for local testing
ssh -i key.pem -L 8000:localhost:8000 ubuntu@<ELASTIC_IP>
```

## Cost Optimization Tips

1. **Reserve Instance**: 1-year no-upfront reserved t3.medium = ~$20/mo (33% savings).
2. **Spot Instances**: t3.medium spot = ~$9/mo (70% savings) but can be interrupted.
3. **Savings Plans**: Compute Savings Plans apply across all EC2 regardless of region/instance family.
4. **Downgrade to t3.small**: If traffic is low, t3.small ($15/mo) halves the cost with MongoDB cache at 512MB.

## Memory Monitoring

Run `docker stats` after deployment. With 4GB RAM, there's comfortable headroom. If containers exceed ~1.5GB each, consider:
- Reducing MongoDB cache in `docker-compose.yml` (`--wiredTigerCacheGB 0.5`)
- Reducing uvicorn workers to 1 (already default in Dockerfile)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Containers won't start" | Check `.env` has all required vars; run `docker compose logs backend` |
| "MongoDB connection refused" | Ensure `mongodb` container is healthy: `docker compose ps` |
| "CORS errors from frontend" | Update `CORS_ORIGINS` in `.env` and restart backend |
| "High CPU/memory" | Check `docker stats`; reduce uvicorn workers in Dockerfile |
| "Out of disk space" | Run `docker system prune -f` to clean unused images |

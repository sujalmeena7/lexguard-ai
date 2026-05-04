# LexGuard AI — AWS EC2 Deployment Guide (ap-south-1)

Cost-optimized deployment using a single EC2 instance with Docker containers.

## Architecture

| Component | Choice | Monthly Cost |
|-----------|--------|-------------|
| Compute | EC2 t3.small (1 vCPU, 2GB) | ~$15 |
| Database | MongoDB 7 Docker sidecar | $0 |
| Storage | 20GB GP3 EBS (root) | ~$1.60 |
| Load Balancer | **None** — Elastic IP only | $0 |
| SSL | **None** — HTTP only (add Caddy later) | $0 |
| **Total** | | **~$17/mo** |

With $200 AWS credits, this runs for **~13 months free**.

> **Note:** t3.small is memory-constrained (2GB RAM). MongoDB cache is capped to 512MB in `docker-compose.yml` to prevent OOM kills. Monitor with `docker stats` under load.

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
- **Instance type**: `t3.small`
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

1. **t3.small is half the cost of t3.medium** ($15 vs $30/mo). Upgrade to t3.medium if you see memory pressure under load.
2. **Reserve Instance**: 1-year no-upfront reserved t3.small = ~$10/mo (33% savings).
3. **Spot Instances**: t3.small spot = ~$4.50/mo (70% savings) but can be interrupted.
4. **Savings Plans**: Compute Savings Plans apply across all EC2 regardless of region/instance family.

## Memory Monitoring (t3.small critical)

Run `docker stats` after deployment. If MongoDB or the backend exceed ~800MB each, containers will restart. Solutions:
- Reduce MongoDB cache further in `docker-compose.yml` (`--wiredTigerCacheSizeGB 0.25`)
- Reduce uvicorn workers to 1 (already default in Dockerfile)
- Upgrade to t3.medium if traffic grows

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Containers won't start" | Check `.env` has all required vars; run `docker compose logs backend` |
| "MongoDB connection refused" | Ensure `mongodb` container is healthy: `docker compose ps` |
| "CORS errors from frontend" | Update `CORS_ORIGINS` in `.env` and restart backend |
| "High CPU/memory" | Check `docker stats`; reduce uvicorn workers in Dockerfile |
| "Out of disk space" | Run `docker system prune -f` to clean unused images |

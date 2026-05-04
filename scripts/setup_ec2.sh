#!/bin/bash
# ============================================================
# LexGuard AI — EC2 Bootstrap Script (ap-south-1 / Mumbai)
# Compute: t3.medium (2 vCPU, 4GB RAM)
# OS: Ubuntu 22.04 LTS
# Storage: 20GB GP3 EBS
#
# Usage:
#   1. Launch EC2 t3.medium in ap-south-1 with Ubuntu 22.04
#   2. Attach 20GB GP3 EBS root volume
#   3. Create Security Group: allow 22 (SSH), 8000 (API), 80/443 (HTTP/HTTPS)
#   4. Allocate & associate an Elastic IP
#   5. SCP this script to the instance: scp -i key.pem setup_ec2.sh ubuntu@<eip>:~
#   6. SSH in and run: chmod +x setup_ec2.sh && ./setup_ec2.sh
# ============================================================

set -euo pipefail

# ---- Configuration ----
APP_DIR="/opt/lexguard"
REPO_URL="https://github.com/sujalmeena7/lexguard-ai.git"
BRANCH="main"
BACKEND_DIR="$APP_DIR/backend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 1. System Update
# ============================================================
log_info "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Install essential tools
sudo apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    ufw \
    jq \
    htop \
    fail2ban

# ============================================================
# 2. GP3 Storage Optimization (if using a separate EBS volume)
# ============================================================
# If you attached a separate 20GB GP3 volume at /dev/xvdf:
# sudo mkfs -t xfs /dev/xvdf
# sudo mkdir -p /data
# sudo mount /dev/xvdf /data
# echo '/dev/xvdf /data xfs defaults,noatime 0 0' | sudo tee -a /etc/fstab
# For single-root-volume setups (default 20GB GP3), no extra action needed.

# ============================================================
# 3. Install Docker & Docker Compose
# ============================================================
log_info "Installing Docker..."
if ! command -v docker &> /dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker ubuntu
    log_info "Docker installed. Re-login required for group changes to take effect."
else
    log_warn "Docker already installed."
fi

# Docker Compose (v2 is included with docker-ce-plugin, verify)
docker compose version || { log_error "Docker Compose not found!"; exit 1; }

# ============================================================
# 4. Firewall (UFW) — Minimal, Cost-Optimized
# ============================================================
log_info "Configuring UFW firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw allow 8000/tcp comment 'FastAPI Backend'
sudo ufw --force enable

# ============================================================
# 5. Clone Repository
# ============================================================
log_info "Cloning LexGuard repository..."
if [ -d "$APP_DIR" ]; then
    log_warn "Directory $APP_DIR exists. Pulling latest changes..."
    cd "$APP_DIR" && sudo git pull origin "$BRANCH"
else
    sudo mkdir -p "$APP_DIR"
    sudo git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

# Set proper ownership
sudo chown -R ubuntu:ubuntu "$APP_DIR"

# ============================================================
# 6. Environment Variables Setup
# ============================================================
log_info "Setting up environment variables..."

# IMPORTANT: You must fill in these values before running the script,
# or the backend will fail to start. The safest way is to create a
# .env file locally and SCP it to the instance BEFORE running this script.
#
# Example:
#   scp -i key.pem backend/.env ubuntu@<elastic-ip>:/opt/lexguard/backend/.env
#
# Required env vars (see backend/server.py for full list):
#   GOOGLE_API_KEY       - Gemini API key (required)
#   SUPABASE_URL         - Supabase project URL
#   SUPABASE_ANON_KEY    - Supabase anon/public key
#   MONGO_URL            - Overridden by docker-compose to mongodb://mongodb:27017/lexguard_db
#   ADMIN_TOKEN          - Admin API token (set this!)
#   GROQ_API_KEY         - Optional Groq fallback key
#   CORS_ORIGINS         - Comma-separated frontend URLs (e.g., https://yourapp.vercel.app)

ENV_FILE="$BACKEND_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    log_warn ".env file not found at $ENV_FILE"
    log_warn "Creating a template .env file. YOU MUST EDIT THIS with real secrets before starting!"

    cat > "$ENV_FILE" << 'EOF'
# === LexGuard AI Backend Environment Variables ===
# ⚠️  WARNING: This is a TEMPLATE. Replace all placeholder values before production use.

# Google Gemini (REQUIRED)
GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY_HERE
GEMINI_MODEL=gemini-2.0-flash

# Supabase Auth (REQUIRED for JWT verification)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# MongoDB (Docker Compose overrides this automatically)
# MONGO_URL=mongodb://mongodb:27017/lexguard_db
DB_NAME=lexguard_db

# Admin Token (REQUIRED for /api/admin endpoints)
ADMIN_TOKEN=change-me-to-a-long-random-string

# Groq Fallback (OPTIONAL)
# GROQ_API_KEY=your-groq-key
# GROQ_MODEL=llama-3.3-70b-versatile

# CORS (REQUIRED — add your Vercel / frontend URLs)
CORS_ORIGINS=https://your-app.vercel.app,https://www.yourdomain.com
# CORS_ORIGIN_REGEX=https://([a-z0-9-]+\.)*vercel\.app$

# Auth Handoff TTL (seconds)
AUTH_HANDOFF_TTL_SECONDS=120

# Render / webhook (optional)
# RENDER_EXTERNAL_URL=https://your-backend.onrender.com
EOF

    log_error "=========================================="
    log_error "STOP: The .env template was created."
    log_error "Edit $ENV_FILE with your REAL secrets, then re-run:"
    log_error "  cd $BACKEND_DIR && docker compose up -d"
    log_error "=========================================="
    exit 1
else
    log_info ".env file found at $ENV_FILE"
fi

# ============================================================
# 7. Docker Compose Build & Launch
# ============================================================
log_info "Building and starting Docker containers..."
cd "$BACKEND_DIR"

# Pull latest MongoDB image
docker compose pull mongodb

# Build and start services
docker compose up --build -d

# ============================================================
# 8. Health Check & Verification
# ============================================================
log_info "Waiting for services to start (30s)..."
sleep 30

log_info "Running health checks..."

# Check MongoDB
if docker compose ps | grep -q "lexguard-mongodb.*running"; then
    log_info "MongoDB container: RUNNING"
else
    log_error "MongoDB container: FAILED — check logs with: docker compose logs mongodb"
fi

# Check Backend
if docker compose ps | grep -q "lexguard-backend.*running"; then
    log_info "Backend container: RUNNING"
else
    log_error "Backend container: FAILED — check logs with: docker compose logs backend"
    exit 1
fi

# API health endpoint
for i in {1..10}; do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        log_info "API health check: PASS"
        break
    fi
    log_warn "API health check attempt $i/10..."
    sleep 5
    if [ "$i" -eq 10 ]; then
        log_error "API failed to respond. Check: docker compose logs backend"
    fi
done

# ============================================================
# 9. Auto-Restart on Boot (Systemd)
# ============================================================
log_info "Enabling Docker auto-start on boot..."
sudo systemctl enable docker

# Create a systemd service for the LexGuard stack
cat > /tmp/lexguard.service << EOF
[Unit]
Description=LexGuard AI Docker Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$BACKEND_DIR
User=root
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/lexguard.service /etc/systemd/system/lexguard.service
sudo systemctl daemon-reload
sudo systemctl enable lexguard.service

# ============================================================
# 10. Cost-Saving & Maintenance Tips
# ============================================================
log_info "=========================================="
log_info "DEPLOYMENT COMPLETE"
log_info "=========================================="
log_info ""
log_info "Backend API:    http://<your-elastic-ip>:8000"
log_info "Health Check:   http://<your-elastic-ip>:8000/health"
log_info ""
log_info "Useful commands:"
log_info "  docker compose logs -f backend    # Stream backend logs"
log_info "  docker compose logs -f mongodb    # Stream MongoDB logs"
log_info "  docker compose down               # Stop all services"
log_info "  docker compose up -d              # Start all services"
log_info "  docker system prune -f            # Clean unused images"
log_info ""
log_info "Security:"
log_info "  - UFW is active (ports 22, 80, 443, 8000 open)"
log_info "  - fail2ban is installed"
log_info "  - MongoDB is bound to localhost ONLY"
log_info ""
log_info "Cost Optimization:"
log_info "  - No ALB ($18/mo saved) — using Elastic IP directly"
log_info "  - No RDS ($30/mo saved) — MongoDB runs in Docker sidecar"
log_info "  - GP3 20GB EBS is the default, cost-efficient storage"
log_info "  - t3.medium ~$30/mo — within your $200 credit budget for ~6 months"
log_info ""
log_info "NEXT STEPS:"
log_info "  1. Update your Vercel frontend CORS_ORIGINS to point to this EC2 IP"
log_info "  2. Consider adding Caddy/Nginx + Let's Encrypt for free HTTPS"
log_info "  3. Set up AWS CloudWatch alarms for CPU/memory usage"
log_info "  4. Enable AWS Backup for the EBS volume"
log_info ""
log_info "=========================================="

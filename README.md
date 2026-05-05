<div align="center">

# ⚖️ LexGuard AI

**Enterprise DPDP Compliance Auditor**

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

AI-powered compliance auditing against India's **Digital Personal Data Protection (DPDP) Act 2023**. Transforms legal documents into actionable risk assessments using tiered RAG + LLM inference.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Contributing](#contributing)

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              Vercel Edge                 │
                    │  ┌──────────────┐    ┌──────────────┐  │
                    │  │   public/    │    │  dashboard/  │  │
                    │  │ Static Site  │    │ Next.js App  │  │
                    │  └──────────────┘    └──────────────┘  │
                    └─────────────────────────────────────────┘
                               │                    │
                               │                    ▼
                               │           ┌─────────────────┐
                               │           │   AWS EC2        │
                               │           │  ┌───────────┐  │
                               │           │  │ FastAPI   │  │
                               │           │  │ Backend   │  │
                               │           │  └─────┬─────┘  │
                               │           │        │        │
                               │           │  ┌─────┴─────┐  │
                               │           │  │ MongoDB   │  │
                               │           │  │ Sidecar   │  │
                               │           │  └───────────┘  │
                               │           └─────────────────┘
                               │
                               ▼
                    ┌─────────────────────────────────────────┐
```

### Data Flow

1. **Landing Page** (`public/`) — Static Vercel site with live audit widget
2. **Dashboard** (`dashboard/`) — Next.js app with Supabase auth, glassmorphism UI
3. **FastAPI Backend** (`backend/`) — Core API on AWS EC2 with MongoDB sidecar
4. **Core Engine** (`core/`) — Shared Python packages

---

## Project Structure

```
lexguard-ai/
├── api/                          # Vercel serverless proxy functions
│   ├── analyze.js                 # POST /api/analyze → EC2
│   ├── config.js                  # GET /api/config → EC2
│   ├── unlock.js                  # POST /api/unlock → EC2
│   └── auth/
│       └── handoff.js             # POST /api/auth/handoff → EC2
│
├── backend/                       # FastAPI backend (AWS EC2)
│   ├── server.py                  # FastAPI app entrypoint
│   ├── Dockerfile                 # Container build
│   ├── docker-compose.yml         # EC2 orchestration
│   └── requirements.txt           # Backend deps
│
├── core/                          # (reserved for future shared modules)
│
├── public/                        # Static landing page (Vercel)
│   ├── index.html
│   ├── css/
│   └── js/
│       ├── widget.js              # Live audit widget
│       └── main.js                # Landing page logic
│
├── dashboard/                     # Next.js dashboard (Vercel)
│   ├── src/app/                   # App Router pages
│   ├── src/components/            # UI components
│   └── public/                    # Static assets
│
├── scripts/                       # DevOps scripts
│   ├── setup_ec2.sh               # EC2 bootstrap
│   └── README-AWS-EC2.md          # Deployment guide
│
├── storage/                       # Runtime data (gitignored)
│   ├── local/                     # User document uploads
│   ├── vector_db/                 # Chroma vector stores
│   ├── workspaces/                # Per-user Chroma DBs
│   └── logs/                      # Application logs
│
├── config/                        # JSON configs
│   └── design_guidelines.json
│
├── vercel.json                    # Vercel routing config
├── .vercelignore                  # Vercel deploy exclusions
├── .gitignore
└── README.md                      # You are here
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend** | FastAPI | 0.115+ |
| | Python | 3.11 |
| | Motor (MongoDB async) | 3.6+ |
| **LLM** | Groq API | 0.11+ |
| | Google GenAI | 1.0+ |
| **Dashboard** | Next.js | 14 |
| | React | 18 |
| | Tailwind CSS | 3.4 |
| | shadcn/ui | — |
| **Frontend** | Vanilla JS | ES2022 |
| | CSS3 | — |
| **Auth** | Supabase | 2.15 |
| **Infra** | Docker + Compose | 3.9 |
| | AWS EC2 (t3.medium) | Ubuntu 22.04 |
| **Reliability** | Tenacity | 8.0+ |
| | SlowAPI | — |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for EC2 deployment)
- Node.js 20+ (for Vercel functions)
- Groq API key
- Supabase project

### Local Development

```bash
# 1. Clone
git clone https://github.com/sujalmeena7/lexguard-ai.git
cd lexguard-ai

# 2. Backend (FastAPI)
cd backend
cp .env.example .env        # Fill in your keys
pip install -r requirements.txt
python server.py            # http://localhost:8000

# 3. Dashboard (Next.js)
cd ../dashboard
npm install
npm run dev                 # http://localhost:3000

# 4. Landing Page (static)
cd ../public
# Serve with any static server, or open index.html directly
```

### Environment Setup

Create `backend/.env`:

```env
# Required
MONGO_URL=mongodb://localhost:27017/lexguard_db
DB_NAME=lexguard_db
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Optional
CORS_ORIGINS=http://localhost:3000,http://localhost:8501
ENVIRONMENT=development
```

---

## Deployment

### AWS EC2 (Backend)

```bash
# One-command bootstrap on fresh Ubuntu 22.04 EC2
curl -fsSL https://raw.githubusercontent.com/sujalmeena7/lexguard-ai/main/scripts/setup_ec2.sh | sudo bash
```

| Spec | Value |
|------|-------|
| Instance | t3.medium (2 vCPU, 4GB) |
| Region | ap-south-1 (Mumbai) |
| OS | Ubuntu 22.04 LTS |
| Cost | ~$30/mo |

See [`scripts/README-AWS-EC2.md`](scripts/README-AWS-EC2.md) for full walkthrough.

### Vercel (Landing Page + API Proxy)

1. Connect GitHub repo to Vercel
2. Framework preset: **Other**
3. Set environment variable: `BACKEND_URL=http://your-ec2-ip:8000`
4. Deploy

### Vercel (Dashboard)

1. Connect GitHub repo to Vercel
2. Framework preset: **Next.js**
3. Root directory: `dashboard/`
4. Set environment variables (see dashboard `.env.local`)
5. Deploy

---

## API Reference

### Public Endpoints (via Vercel proxy)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/config` | Public config (Supabase URL, anon key) |
| `POST` | `/api/analyze` | Run compliance audit on policy text |
| `POST` | `/api/unlock` | Unlock full report (email gate) |
| `POST` | `/api/auth/handoff` | Exchange Supabase token for session |

### Backend Endpoints (EC2)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/analyze` | — | Analyze policy text |
| `POST` | `/api/unlock` | — | Unlock full audit |
| `POST` | `/api/auth/handoff` | Bearer | Token handoff |
| `POST` | `/api/roadmap` | Bearer | Generate privacy roadmap |
| `GET` | `/api/config` | — | Public configuration |

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m "feat: add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

### Commit Convention

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `refactor:` Code restructuring
- `chore:` Maintenance tasks

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built by [Sujal Meena](https://linkedin.com/in/sujalmeena7)**

</div>

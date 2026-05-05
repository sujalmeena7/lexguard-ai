# LexGuard AI Dashboard — Deployment Guide

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Vercel                                   │
│  ┌──────────────────────┐    ┌────────────────────────────────┐  │
│  │ Landing Page (/)     │    │ Next.js Dashboard (/dashboard)│  │
│  │  public/index.html   │───→│  dashboard/                   │  │
│  │  Static site         │    │  Next.js 16 + App Router      │  │
│  └──────────────────────┘    └────────────────────────────────┘  │
│           │                           │                         │
│           └───────────┬───────────────┘                         │
│                       │                                          │
│              ┌────────┴────────┐                                │
│              │  Vercel API     │                                │
│              │  api/*.js       │                                │
│              └────────┬────────┘                                │
└───────────────────────┼────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AWS EC2 (t3.medium)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend  (Port 8000)                            │   │
│  │  - /api/analyze          → Document analysis            │   │
│  │  - /api/analyze/stream   → SSE real-time progress       │   │
│  │  - /api/auth/handoff     → Create handoff code          │   │
│  │  - /api/auth/handoff/exchange → Exchange for token      │   │
│  │  - MongoDB sidecar                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Supabase                                     │
│  - Authentication (email/password, OAuth)                        │
│  - PostgreSQL database (audit logs, user profiles)              │
│  - Row Level Security (RLS)                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Steps

### 1. Environment Variables

Create `.env.local` in `dashboard/`:

```bash
# Supabase (same project as landing page)
NEXT_PUBLIC_SUPABASE_URL=https://corbyaeuxflemgilgcom.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...

# Backend EC2 (FastAPI)
NEXT_PUBLIC_BACKEND_URL=http://65.1.207.29:8000

# Landing page URL (for "back to landing" link)
NEXT_PUBLIC_LANDING_URL=https://lexguard-ai.vercel.app
```

> **Note**: `NEXT_PUBLIC_` prefix exposes these to the browser. Only put public-safe values there.

### 2. Deploy to Vercel

#### Option A: New Vercel Project (Recommended)

```bash
cd dashboard
vercel --prod
```

Set the **Root Directory** to `dashboard/` in Vercel project settings.

Add environment variables in Vercel Dashboard → Settings → Environment Variables.

#### Option B: Merge with Landing Page (Same Project)

Move `dashboard/` contents to project root and update `vercel.json`:

```json
{
  "framework": "nextjs",
  "buildCommand": "cd dashboard && npm run build",
  "outputDirectory": "dashboard/.next"
}
```

### 3. Update Landing Page

After deployment, update `public/index.html`:

```javascript
window.ENV_DASHBOARD_URL = 'https://YOUR-DASHBOARD-URL.vercel.app/';
```

Push this change so the landing page widget redirects to the new dashboard.

### 4. Verify Auth Handoff

1. Sign in on landing page
2. Click "Dashboard" → opens Next.js dashboard with `?handoff_code=xxx`
3. Dashboard exchanges code for session via `POST /api/auth/handoff/exchange`
4. User is automatically signed in — no password re-entry

### 5. Local Development

```bash
# Terminal 1 — Backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2 — Dashboard
cd dashboard
npm run dev

# Terminal 3 — Landing page (optional)
cd public
npx serve
```

Landing page at `http://localhost:3000` (or 8080)
Dashboard at `http://localhost:3000`
Backend at `http://localhost:8000`

## Auth Flow

```
Landing Page ──sign in──→ Supabase Auth
     │                           │
     │  1. get access_token       │
     │  2. POST /auth/handoff     │
     │     → handoff_code         │
     │                           │
     ▼                           │
Open dashboard/?handoff_code=xxx  │
     │                           │
     │  3. POST /auth/handoff/exchange
     │     → access_token         │
     │  4. setSession(token)     │
     │                           │
     ▼                           ▼
User is authenticated on both apps
```

## Production Checklist

- [ ] Update `NEXT_PUBLIC_BACKEND_URL` to HTTPS with domain
- [ ] Add CORS origin for dashboard URL in `backend/server.py`
- [ ] Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] Configure Vercel Analytics (optional)
- [ ] Enable Vercel Edge Network caching for static assets
- [ ] Test auth handoff end-to-end
- [ ] Test file upload → analysis → results flow

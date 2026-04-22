# LexGuard AI — Product Requirements Document

## Original Problem Statement
Add an inline "Try it now" hero widget to the LexGuard AI landing page. User pastes a privacy policy → gets a real DPDP verdict in 2 seconds → sees flagged clauses + score → email gate unlocks full report. Follow-up: fix CTA, rate-limit Groq, index Mongo, build admin view.

## Architecture
- **Backend** (FastAPI /app/backend/server.py): `/api/analyze`, `/api/unlock`, `/api/leads/count`, `/api/admin/*`. Groq (llama-3.3-70b-versatile). MongoDB `analyses` + `leads`. Rate limiter via slowapi (proxy-aware X-Forwarded-For). Indexes on startup.
- **Frontend** (static HTML in /app/frontend/public/):
  - `index.html` — landing page with live hero widget
  - `admin.html` — token-gated admin SPA (stats + leads table + detail modal)
  - `js/widget.js`, `css/widget.css`, `js/main.js`
  - React App.js returns null (landing is pure HTML)

## What's Been Implemented

### Iteration 1 (Jan 2026)
- [x] Live hero widget replacing static terminal mockup
- [x] `POST /api/analyze` — Groq DPDP audit, returns score + 2-clause preview
- [x] `POST /api/unlock` — stores lead in MongoDB, returns full report (all clauses + 6-focus checklist)
- [x] 5 widget states (input / loading / preview / full / error)
- [x] MongoDB persistence (ephemeral text — raw policy never stored)
- [x] 15/15 backend pytest + full Playwright E2E (100% pass)

### Iteration 2 (Jan 2026)
- [x] **Bug fix**: Hero "Try a Live Audit" CTA now scrolls, focuses the textarea, and flashes the widget border (visible feedback even when widget already in view)
- [x] **Rate limiting** on `/api/analyze` (5/min, 30/hour per IP), `/api/unlock` (20/min), `/api/admin/login` (10/min). Proxy-aware using X-Forwarded-For.
- [x] **MongoDB indexes** — `analyses.analysis_id` (unique), `analyses.created_at`, `leads.email`, `leads.lead_id` (unique), `leads.created_at`, `leads.analysis_id`. Auto-created on startup.
- [x] **Admin API**: `/api/admin/login`, `/api/admin/stats`, `/api/admin/leads`, `/api/admin/lead/{id}` — protected by `X-Admin-Token` header.
- [x] **Admin SPA** at `/admin.html` — token login, live stats dashboard (total leads, audits, conversion rate, 24h counters), leads table with click-to-detail modal.

## P1 / Backlog
- Migrate deprecated `@app.on_event` → FastAPI lifespan context
- Token-level SSE streaming of Groq output (replace fake log lines)
- Email delivery of unlocked reports (Resend)
- PDF export of full report
- Drip email sequence to captured leads
- CSV export of leads from admin page

## User Personas
- **End user (landing visitor)**: Indian founder/legal counsel pasting privacy policy for a quick DPDP check
- **Admin (Sujal)**: Sole product owner monitoring lead flow + conversion

## Credentials
- `GROQ_API_KEY`, `ADMIN_TOKEN=lexguard-admin-2026` in `/app/backend/.env`
- Admin login: `${REACT_APP_BACKEND_URL}/admin.html` → token `lexguard-admin-2026`

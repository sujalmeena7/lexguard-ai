# LexGuard AI — Product Requirements Document

## Original Problem Statement
Add an inline "Try it now" hero widget to the LexGuard AI landing page. User pastes a privacy policy → gets a real DPDP verdict in 2 seconds → sees flagged clauses + score → email gate. Follow-ups: fix CTA, rate-limit Groq, index Mongo, build admin view, redirect unlock to Streamlit dashboard, expose Launch Dashboard CTAs.

## Architecture
- **Backend** (FastAPI /app/backend/server.py): `/api/analyze`, `/api/unlock`, `/api/leads/count`, `/api/admin/*`. Groq (llama-3.3-70b-versatile). MongoDB `analyses` + `leads`. Rate limiter via slowapi (proxy-aware X-Forwarded-For). Indexes on startup.
- **Frontend** (static HTML in /app/frontend/public/):
  - `index.html` — landing page with live hero widget
  - `admin.html` — token-gated admin SPA
  - `js/widget.js`, `css/widget.css`, `js/main.js`
- **External**: Streamlit dashboard at https://lexguard-ai-a8kv79qhvngwsute9api2n.streamlit.app

## What's Been Implemented

### Iteration 1 (Jan 2026)
- [x] Live hero widget replacing static terminal mockup
- [x] `POST /api/analyze` + `POST /api/unlock` — Groq-powered DPDP audit
- [x] 5 widget states: input / loading / preview / full / error
- [x] 15/15 backend pytest + full Playwright E2E

### Iteration 2 (Jan 2026)
- [x] Hero CTA bug fix (focuses textarea + flashes widget border)
- [x] Rate limiting (slowapi, proxy-aware): analyze=5/min+30/hour, unlock=20/min, admin-login=10/min
- [x] MongoDB indexes (analyses.analysis_id unique, leads.email, etc.)
- [x] Admin API + Admin SPA at /admin.html (login, stats dashboard, leads table, detail modal)

### Iteration 3 (Jan 2026)
- [x] **"Launch Dashboard" CTAs** added to: nav bar, hero secondary button, final CTA, footer Product section — all pointing to Streamlit URL in new tab
- [x] **Email-gate flow changed**: after user submits email, widget now opens Streamlit dashboard in a new tab + shows "Opening the full dashboard…" state (no free full report anymore)
- [x] Email still captured in MongoDB leads collection (source: hero_try_it_now) — admin can see all captured emails
- [x] Gate copy updated: "Launch the full LexGuard Dashboard" / button says "Launch Dashboard"

## User Flow (final)
1. Visit landing → paste policy or click "Try a sample clause"
2. Click "Run DPDP Audit" → Groq analyzes (< 2s)
3. See compliance score (0-100) + verdict + 2 flagged clauses with suggested fixes (preview)
4. Enter email → click "Launch Dashboard"
5. Email saved in MongoDB + Streamlit dashboard opens in new tab for deeper audits (PDF upload, full reports, etc.)

## User Personas
- **End user**: Indian founder/legal counsel → quick audit → wants the full Streamlit power tool
- **Admin (Sujal)**: Owns the lead funnel → `/admin.html` (token in `backend/.env` as `ADMIN_TOKEN`, never committed)

## Credentials
- `GROQ_API_KEY`, `ADMIN_TOKEN`, `GOOGLE_API_KEY` — see `/app/backend/.env` (gitignored)
- Admin: `${REACT_APP_BACKEND_URL}/admin.html`
- Streamlit: `https://lexguard-ai-a8kv79qhvngwsute9api2n.streamlit.app`

## P1 / Backlog
- Migrate deprecated `@app.on_event` → FastAPI lifespan context
- CSV export from admin page
- SSE streaming for Groq output
- Pass captured email as URL param to Streamlit (?lead=email) so Streamlit can auto-track conversion
- Payment gateway (Razorpay) for premium Streamlit features

## Future / Backlog
- Drip email to captured leads via Resend
- Analytics funnel chart (paste → analyze → email → Streamlit open) on admin page
- A/B testing email-gate copy variants

### Iteration 4 (Jan 2026)
- [x] **Lead email passed to Streamlit** — widget opens `${STREAMLIT_URL}/?lead=<email>&src=landing&analysis=<analysis_id>` on unlock submit. Streamlit app can read query params for auto-tracking & personalization.
- [x] **CSV export** — `GET /api/admin/leads.csv?token=<ADMIN_TOKEN>` streams CSV with columns: lead_id, email, name, company, analysis_id, compliance_score, verdict, total_clauses_flagged, source, created_at. "Export CSV" button added to admin page (gold-accented).
- [x] **+1 Credit granted badge** — prominent green/gold gradient reward badge in redirect state with pulsing gift icon. Headline: "+1 free audit credit granted". CTA copy updated to "Open Dashboard & claim credit". Framing: email capture = user gains something (1-free-audit credit), reduces friction.

## Known Issue
⚠ Groq free tier = 100K tokens/day (TPD). If quota is hit, `/api/analyze` returns 502 until quota resets (~24h) or user upgrades at https://console.groq.com/settings/billing.

# LexGuard AI — Product Requirements Document

## Original Problem Statement
Add an inline "Try it now" hero widget to the LexGuard AI landing page (repo: https://github.com/sujalmeena7/lexguard-ai). Replace the static terminal mockup with a live text box. User pastes any paragraph of a privacy policy → gets a real DPDP verdict in 2 seconds → sees flagged clauses + a score → is prompted "Enter email to unlock full report." Uses Groq (Llama 3.3 70B) for fast inference.

## User Preferences (captured at kickoff)
- Groq API key: provided by user
- Email storage: MongoDB (leads collection) + show full report in-app (no email sending)
- Full report: all flagged clauses + recommendations + DPDP 6-point checklist
- Preview: 2 flagged clauses + compliance score (0-100) + verdict
- DPDP focus areas: Consent, Notice, Purpose Limitation, Data Minimization, Data Principal Rights, Breach Notification

## Architecture
- **Backend**: FastAPI at /app/backend/server.py — endpoints `POST /api/analyze`, `POST /api/unlock`, `GET /api/leads/count`. Groq AsyncGroq client (model: llama-3.3-70b-versatile) with JSON-object response_format. MongoDB collections: `analyses` (full analysis cached by analysis_id), `leads` (captured emails).
- **Frontend**: Static landing page served from /app/frontend/public/index.html (CRA's public folder). Widget HTML/CSS/JS: /app/frontend/public/css/widget.css + /app/frontend/public/js/widget.js. React App.js returns null — landing is pure HTML/CSS/JS for fast load. Uses relative `/api` paths (ingress routes to backend).

## Widget States
1. **input** — textarea + "Run DPDP Audit" + "Try a sample clause"
2. **loading** — animated log lines + progress bar
3. **preview** — compliance score (serif 48px), colored verdict pill, score bar, summary quote, 2 flagged clause cards with risk chips + DPDP section refs + excerpts + suggested fixes, email gate
4. **full** (post-unlock) — all flagged clauses + tabbed DPDP 6-point checklist
5. **error** — retry

## What's Been Implemented (Jan 2026)
- [x] Inline hero "Try it now" widget replacing static terminal mockup
- [x] Real-time Groq-powered DPDP 2023 analysis (< 2s)
- [x] Compliance score 0-100 with LOW / MODERATE / HIGH RISK verdict
- [x] 2-clause preview → email gate → full report unlock
- [x] 6-focus-area DPDP checklist (Consent, Notice, Purpose Limitation, Data Minimization, Data Principal Rights, Breach Notification)
- [x] MongoDB persistence (analyses + leads)
- [x] Raw policy text NOT retained — ephemeral processing (matches "never used to train models" copy)
- [x] Responsive design (mobile-friendly)
- [x] Full test coverage: 15/15 backend pytest + full Playwright E2E (100% pass)

## P1 / Backlog
- Rate limiting on /api/analyze (prevent Groq abuse)
- MongoDB indexes on analyses.analysis_id + leads.email
- SSE streaming of Groq output for token-by-token display
- Admin dashboard to view captured leads
- Email delivery of full report (Resend/SendGrid)
- PDF export of unlocked report
- Migrate deprecated @app.on_event('shutdown') → lifespan handler

## P2 / Future
- Multi-document batch analysis
- Client-side SSE progress instead of fake log lines
- Paywall tiers (free audits/month → paid enterprise)
- A/B test email gate copy
- Analytics on conversion rate (paste → analyze → unlock)

/* ============================================================
   LexGuard AI — Live Audit Widget (hero "Try it Now")
   - Paste → /api/analyze → preview (score + 2 clauses)
   - Email gate → /api/unlock → full report (all clauses + checklist)
   ============================================================ */
(() => {
    'use strict';

    const BACKEND = (window.__LEXGUARD_BACKEND__ || '').replace(/\/+$/, '');
    const API = (BACKEND ? BACKEND : '') + '/api';
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const STREAMLIT_URL = isLocalhost ? 'http://localhost:8501' : 'https://lexguard-ai-a8kv79qhvngwsute9api2n.streamlit.app';

    const SAMPLE_POLICY = `We may collect, process, store, and share your personal data — including your name, email, phone number, location, browsing behaviour, device identifiers, and financial information — with our affiliates, business partners, marketing agencies, and any third-party service providers for purposes we deem necessary, in perpetuity. By using this service, you are deemed to have given your consent to all current and any future uses of your data, even if our policy changes without prior notice. We may retain your data indefinitely, even after your account is closed, and we reserve the right not to respond to requests for data deletion if we believe retention serves a legitimate business interest. In the event of a data breach, we will evaluate on a case-by-case basis whether notification is warranted.`;

    const LOG_LINES = [
        'ingesting document · tokenizing…',
        'vectorising against DPDP §6 clause library',
        'routing to gemini-2.0-flash… (groq fallback if >3s)',
        'cross-referencing DPDP Act 2023 obligations',
        'scoring compliance · ranking risks',
    ];

    document.addEventListener('DOMContentLoaded', () => {
        const widget = document.getElementById('lg-widget');
        if (!widget) return;

        const els = {
            input: document.getElementById('lg-input'),
            charCount: document.getElementById('lg-char-count'),
            sampleBtn: document.getElementById('lg-sample-btn'),
            analyzeBtn: document.getElementById('lg-analyze-btn'),
            log: document.getElementById('lg-log'),
            progressBar: document.getElementById('lg-progress-bar'),
            latency: document.getElementById('lg-latency'),
            scoreNum: document.getElementById('lg-score-num'),
            scoreLabel: document.getElementById('lg-score-label'),
            scoreBarFill: document.getElementById('lg-score-bar-fill'),
            verdict: document.getElementById('lg-verdict'),
            summary: document.getElementById('lg-summary'),
            clauses: document.getElementById('lg-clauses'),
            clausesFull: document.getElementById('lg-clauses-full'),
            checklist: document.getElementById('lg-checklist'),
            previewCount: document.getElementById('lg-preview-count'),
            totalCount: document.getElementById('lg-total-count'),
            gateForm: document.getElementById('lg-gate-form'),
            gateEmail: document.getElementById('lg-gate-email'),
            resetBtn: document.getElementById('lg-reset-btn'),
            resetBtn2: document.getElementById('lg-reset-btn-2'),
            errorMsg: document.getElementById('lg-error-msg'),
            errorRetry: document.getElementById('lg-error-retry'),
        };

        let state = {
            analysisId: null,
            previewData: null,
        };

        // ---------- helpers ----------
        const getSessionAccessToken = async () => {
            try {
                let client = window.__LG_SUPABASE__;

                if (!client) {
                    for (let i = 0; i < 20; i++) {
                        await new Promise(r => setTimeout(r, 100));
                        client = window.__LG_SUPABASE__;
                        if (client) break;
                    }
                }
                if (!client) return null;

                const { data: { session }, error } = await client.auth.getSession();
                if (error || !session || !session.access_token) return null;
                return session.access_token;
            } catch (_e) {
                return null;
            }
        };

        const getAuthHeader = async () => {
            try {
                const accessToken = await getSessionAccessToken();
                return accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {};
            } catch (e) {
                console.error('[LexGuard] Auth helper crashed:', e);
                return {};
            }
        };

        const createAuthHandoffCode = async (accessToken) => {
            if (!accessToken) return null;
            try {
                const response = await fetch(`${API}/auth/handoff`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${accessToken}` },
                });
                if (!response.ok) return null;
                const data = await response.json();
                return data?.handoff_code || null;
            } catch (_err) {
                return null;
            }
        };

        const buildStreamlitUrl = async (email) => {
            const url = new URL(`${STREAMLIT_URL}/`);
            url.searchParams.set('lead', email);
            url.searchParams.set('src', 'landing');
            url.searchParams.set('analysis', state.analysisId || '');

            const accessToken = await getSessionAccessToken();
            if (accessToken) {
                const handoffCode = await createAuthHandoffCode(accessToken);
                if (handoffCode) {
                    url.searchParams.set('handoff_code', handoffCode);
                }
            }
            return url.toString();
        };

        const showState = (name) => {
            console.log('[LexGuard] Switching state to:', name);
            widget.querySelectorAll('.lg-state').forEach(s => {
                s.hidden = s.dataset.lgState !== name;
            });
        };

        const isValidEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(v || '').trim());

        const verdictClass = (v) => {
            const up = (v || '').toUpperCase();
            if (up.includes('LOW')) return 'lg-v-low';
            if (up.includes('HIGH')) return 'lg-v-high';
            return 'lg-v-mod';
        };

        const riskChip = (level) => {
            const l = (level || '').toLowerCase();
            if (l.startsWith('high')) return { cls: 'lg-chip-high', label: 'HIGH RISK' };
            if (l.startsWith('med')) return { cls: 'lg-chip-med', label: 'MEDIUM' };
            return { cls: 'lg-chip-low', label: 'LOW' };
        };

        const renderClauseCard = (c) => {
            const chip = riskChip(c.risk_level);
            const card = document.createElement('div');
            card.className = 'lg-clause';
            card.setAttribute('data-testid', 'lg-clause-card');
            card.innerHTML = `
                <div class="lg-clause-head">
                    <span class="lg-chip ${chip.cls}">${chip.label}</span>
                    <span class="lg-clause-id">${escapeHtml(c.clause_id || 'Clause')}</span>
                    <span class="lg-clause-section">${escapeHtml(c.dpdp_section || '')}</span>
                </div>
                ${c.clause_excerpt ? `<div class="lg-clause-excerpt">&ldquo;${escapeHtml(c.clause_excerpt)}&rdquo;</div>` : ''}
                <div class="lg-clause-issue">${escapeHtml(c.issue || '')}</div>
                ${c.suggested_fix ? `<div class="lg-clause-fix"><strong>SUGGESTED FIX</strong>${escapeHtml(c.suggested_fix)}</div>` : ''}
            `;
            return card;
        };

        const escapeHtml = (s) => String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

        const statusIcon = (st) => {
            const s = (st || '').toLowerCase();
            if (s.includes('non')) return { cls: 'bad',  glyph: '✕' };
            if (s.includes('partial')) return { cls: 'part', glyph: '~' };
            if (s.includes('not')) return { cls: 'na',   glyph: '—' };
            return { cls: 'ok', glyph: '✓' };
        };

        const statusClass = (st) => {
            const s = (st || '').toLowerCase();
            if (s.includes('non')) return 'bad';
            if (s.includes('partial')) return 'part';
            if (s.includes('not')) return 'na';
            return 'ok';
        };

        const renderChecklist = (items) => {
            if (!els.checklist) return;
            els.checklist.innerHTML = '';
            (items || []).forEach(it => {
                const row = document.createElement('div');
                row.className = 'lg-check-item';
                row.setAttribute('data-testid', 'lg-check-item');
                const ic = statusIcon(it.status);
                row.innerHTML = `
                    <span class="lg-check-icon ${ic.cls}">${ic.glyph}</span>
                    <div class="lg-check-body">
                        <div class="lg-check-area">${escapeHtml(it.focus_area)}</div>
                        <div class="lg-check-note">${escapeHtml(it.note)}</div>
                    </div>
                    <span class="lg-check-status ${statusClass(it.status)}">${escapeHtml((it.status || '').toUpperCase())}</span>
                `;
                els.checklist.appendChild(row);
            });
        };

        // ---------- input state wiring ----------
        const updateCharCount = () => {
            const len = (els.input.value || '').length;
            els.charCount.textContent = len.toLocaleString('en-IN');
            els.analyzeBtn.disabled = len < 50;
        };
        els.input.addEventListener('input', updateCharCount);
        updateCharCount();

        els.sampleBtn.addEventListener('click', () => {
            els.input.value = SAMPLE_POLICY;
            els.input.focus();
            updateCharCount();
        });

        // ---------- analyze ----------
        const runAnalyze = async () => {
            const policyText = (els.input.value || '').trim();
            if (policyText.length < 50) return;

            showState('loading');
            els.log.innerHTML = '';
            els.progressBar.style.width = '0%';
            els.progressBar.classList.add('lg-bar-animated');
            const pctEl = document.getElementById('lg-progress-pct');
            if (pctEl) { pctEl.textContent = '0%'; pctEl.classList.remove('lg-pct-done'); }

            const started = performance.now();
            let progressIdx = 0;
            let currentPct = 0;
            let targetPct = 0;
            let rafId = null;

            const animateBar = () => {
                const diff = targetPct - currentPct;
                currentPct += diff * 0.12;
                if (Math.abs(diff) < 0.5) currentPct = targetPct;
                els.progressBar.style.width = currentPct + '%';
                if (pctEl) pctEl.textContent = Math.round(currentPct) + '%';
                if (currentPct !== targetPct) rafId = requestAnimationFrame(animateBar);
            };
            const setTarget = (v) => { targetPct = v; cancelAnimationFrame(rafId); rafId = requestAnimationFrame(animateBar); };

            const logInterval = setInterval(() => {
                if (progressIdx >= LOG_LINES.length) return;
                const li = document.createElement('li');
                li.textContent = LOG_LINES[progressIdx];
                els.log.appendChild(li);
                progressIdx++;
                setTarget(Math.min(88, progressIdx * 17.5));
            }, 320);

            const originalBtnHtml = els.analyzeBtn.innerHTML;
            els.analyzeBtn.disabled = true;
            els.analyzeBtn.innerHTML = '<i class="ph-spinner-gap ph-bold lg-spin"></i> Checking security...';

            try {
                console.log('[LexGuard] Starting analysis...');
                const authHeader = await getAuthHeader();
                
                if (!authHeader.Authorization) {
                    console.log('[LexGuard] Unauthenticated attempt. Opening auth modal.');
                    clearInterval(logInterval);
                    cancelAnimationFrame(rafId);
                    els.progressBar.classList.remove('lg-bar-animated');
                    const authBtn = document.querySelector('[data-open-modal="auth"]');
                    if (authBtn) {
                        authBtn.click();
                    } else {
                        alert('Please sign in to run audits.');
                    }
                    showState('input');
                    els.analyzeBtn.disabled = false;
                    els.analyzeBtn.innerHTML = originalBtnHtml;
                    return;
                }
                
                els.analyzeBtn.disabled = false;
                els.analyzeBtn.innerHTML = originalBtnHtml;

                console.log('[LexGuard] Token found. Calling backend...');
                const resp = await fetch(`${API}/analyze`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        ...authHeader
                    },
                    body: JSON.stringify({ policy_text: policyText }),
                });

                clearInterval(logInterval);
                cancelAnimationFrame(rafId);

                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({ detail: 'Request failed' }));
                    throw new Error(err.detail || `HTTP ${resp.status}`);
                }

                const data = await resp.json();
                els.progressBar.classList.remove('lg-bar-animated');
                els.progressBar.style.width = '100%';
                if (pctEl) { pctEl.textContent = '100%'; pctEl.classList.add('lg-pct-done'); }

                // Mark remaining logs as done
                LOG_LINES.slice(progressIdx).forEach(line => {
                    const li = document.createElement('li');
                    li.textContent = line;
                    els.log.appendChild(li);
                });
                els.log.querySelectorAll('li').forEach(li => li.classList.add('ok'));

                const elapsed = ((performance.now() - started) / 1000).toFixed(2);

                state.analysisId = data.analysis_id;
                state.previewData = data;

                await new Promise(r => setTimeout(r, 350));
                renderPreview(data, elapsed);
            } catch (e) {
                clearInterval(logInterval);
                cancelAnimationFrame(rafId);
                els.progressBar.classList.remove('lg-bar-animated');
                els.errorMsg.textContent = e.message || 'Analysis failed. Please try again.';
                showState('error');
            }
        };

        const renderPreview = (data, elapsed) => {
            els.latency.textContent = `${elapsed}s`;
            els.scoreNum.textContent = data.compliance_score;
            els.scoreBarFill.style.width = data.compliance_score + '%';
            els.verdict.className = `lg-verdict ${verdictClass(data.verdict)}`;
            els.verdict.querySelector('.lg-verdict-text').textContent = data.verdict;
            els.summary.textContent = data.summary;

            els.clauses.innerHTML = '';
            (data.flagged_clauses || []).forEach(c => els.clauses.appendChild(renderClauseCard(c)));
            els.previewCount.textContent = (data.flagged_clauses || []).length;
            els.totalCount.textContent = data.total_clauses_flagged;

            showState('preview');
        };

        els.analyzeBtn.addEventListener('click', runAnalyze);
        els.errorRetry.addEventListener('click', () => showState('input'));

        // ---------- email gate ----------
        els.gateForm.addEventListener('submit', async (evt) => {
            evt.preventDefault();
            const email = (els.gateEmail.value || '').trim();
            if (!isValidEmail(email)) {
                els.gateEmail.classList.add('invalid');
                els.gateEmail.focus();
                return;
            }
            els.gateEmail.classList.remove('invalid');

            if (!state.analysisId) return;

            const submitBtn = els.gateForm.querySelector('button[type="submit"]');
            const originalHtml = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="ph ph-spinner-gap"></i> Unlocking…';

            try {
                const authHeader = await getAuthHeader();
                const resp = await fetch(`${API}/unlock`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        ...authHeader
                    },
                    body: JSON.stringify({ analysis_id: state.analysisId, email }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({ detail: 'Unlock failed' }));
                    throw new Error(err.detail || `HTTP ${resp.status}`);
                }
                
                // Email saved — show redirect state and open Streamlit in new tab
                // Pass lead email + analysis_id so Streamlit can auto-track conversion
                const streamlitUrl = await buildStreamlitUrl(email);
                showState('full');
                
                // Update the fallback link href to also carry the lead param
                document.querySelectorAll('[data-testid="lg-redirect-cta"], [data-testid="lg-redirect-fallback"]').forEach(el => {
                    if (el.tagName === 'A') el.href = streamlitUrl;
                });
                
                const newTab = window.open(streamlitUrl, '_blank', 'noopener');
                if (!newTab) {
                    const sub = document.getElementById('lg-redirect-sub');
                    if (sub) sub.textContent = "Popup blocked — click the button below to launch the dashboard manually.";
                }
            } catch (e) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHtml;
                els.errorMsg.textContent = e.message || 'Something went wrong. Please try again.';
                showState('error');
            }
        });

        els.gateEmail.addEventListener('input', () => els.gateEmail.classList.remove('invalid'));

        // ---------- reset ----------
        const reset = () => {
            state.analysisId = null;
            state.previewData = null;
            els.input.value = '';
            els.gateEmail.value = '';
            updateCharCount();
            showState('input');
        };
        els.resetBtn.addEventListener('click', reset);
        els.resetBtn2.addEventListener('click', reset);
    });
})();

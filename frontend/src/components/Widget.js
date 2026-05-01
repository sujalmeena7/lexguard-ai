import { useState, useCallback, useRef } from "react";

const BACKEND = (window.__LEXGUARD_BACKEND__ || "").replace(/\/+$/, "");
const API = BACKEND ? BACKEND + "/api" : "";

const SAMPLE_POLICY = `SwiftCart Solutions Pvt. Ltd. Privacy Policy & Data Handling Agreement...
[Sample privacy policy text for demonstration]`;

export default function Widget() {
  const [input, setInput] = useState("");
  const [state, setState] = useState("input"); // input, loading, preview, error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [progress, setProgress] = useState(0);
  const progressRef = useRef(null);
  const abortRef = useRef(false);

  const charCount = input.length;
  const minChars = 50;

  const animateProgress = () => {
    let current = 0;
    abortRef.current = false;
    const step = () => {
      if (abortRef.current) return;
      current += Math.random() * 2 + 0.5;
      if (current > 95) current = 95;
      setProgress(current);
      if (current < 95) {
        progressRef.current = requestAnimationFrame(step);
      }
    };
    progressRef.current = requestAnimationFrame(step);
  };

  const runAnalyze = useCallback(async () => {
    const policyText = input.trim();
    if (policyText.length < minChars) return;

    if (!API) {
      setErrorMsg("Backend URL is not configured.");
      setState("error");
      return;
    }

    setState("loading");
    setProgress(0);
    animateProgress();

    try {
      const headers = { "Content-Type": "application/json" };
      const token = localStorage.getItem("sb-access-token");
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const resp = await fetch(`${API}/analyze`, {
        method: "POST",
        headers,
        body: JSON.stringify({ policy_text: policyText }),
      });

      abortRef.current = true;
      if (progressRef.current) cancelAnimationFrame(progressRef.current);
      setProgress(100);

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${resp.status}`);
      }

      const data = await resp.json();
      setResult(data);
      setState("preview");
    } catch (err) {
      abortRef.current = true;
      if (progressRef.current) cancelAnimationFrame(progressRef.current);
      setErrorMsg(err.message || "Analysis failed. Please retry.");
      setState("error");
    }
  }, [input]);

  return (
    <section id="audit-widget" className="relative z-10 py-8 md:py-12 px-4 md:px-6 flex justify-center">
      <div className="max-w-4xl mx-auto w-full">
        <div className="liquid-glass rounded-2xl p-4 md:p-8 lg:p-12">
          <div className="flex items-center gap-3 mb-6">
            <span className={`w-2 h-2 rounded-full ${state === "loading" ? "bg-yellow-400 animate-pulse" : state === "preview" ? "bg-green-400" : state === "error" ? "bg-red-400" : "bg-green-400"}`} />
            <span className="text-white/60 text-sm font-mono tracking-wide">
              {state === "input" && "audit.live — paste-to-analyze"}
              {state === "loading" && "audit.live — in progress"}
              {state === "preview" && "audit.report"}
              {state === "error" && "audit.failed"}
            </span>
          </div>

          {state === "input" && (
            <>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Paste a privacy policy or data-processing agreement to audit against India's DPDP Act 2023..."
                className="w-full h-48 bg-black/20 rounded-xl p-4 text-white placeholder:text-white/30 text-sm resize-none outline-none border border-white/10 focus:border-white/30 transition-colors"
              />
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mt-4 gap-3">
                <span className="text-white/40 text-xs shrink-0">{charCount} chars {charCount < minChars && `(min ${minChars})`}</span>
                <div className="flex gap-3 w-full sm:w-auto">
                  <button
                    onClick={() => { setInput(SAMPLE_POLICY); }}
                    className="text-white/50 hover:text-white text-sm transition-colors flex-1 sm:flex-none text-center"
                  >
                    Load sample
                  </button>
                  <button
                    onClick={runAnalyze}
                    disabled={charCount < minChars}
                    className="bg-white text-black rounded-full px-5 py-2 text-sm font-semibold hover:bg-white/90 disabled:opacity-30 disabled:cursor-not-allowed transition-opacity flex-1 sm:flex-none whitespace-nowrap"
                  >
                    Run DPDP Audit
                  </button>
                </div>
              </div>
            </>
          )}

          {state === "loading" && (
            <div className="py-12">
              <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-4">
                <div
                  className="h-full bg-gradient-to-r from-blue-400 to-purple-400 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-white/40 text-sm text-center">Analyzing clauses against DPDP Act 2023...</p>
            </div>
          )}

          {state === "preview" && result && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <p className="text-white/60 text-sm">Compliance Score</p>
                  <p className="text-3xl sm:text-4xl font-bold text-white">{result.compliance_score}%</p>
                </div>
                <div className={`px-4 py-2 rounded-full text-sm font-medium shrink-0 ${result.verdict === "Compliant" ? "bg-green-500/20 text-green-300" : result.verdict === "Non-Compliant" ? "bg-red-500/20 text-red-300" : "bg-yellow-500/20 text-yellow-300"}`}>
                  {result.verdict}
                </div>
              </div>

              {result.flagged_clauses?.length > 0 && (
                <div className="space-y-3">
                  <p className="text-white/60 text-sm">Flagged Clauses ({result.flagged_clauses.length})</p>
                  {result.flagged_clauses.slice(0, 2).map((clause, i) => (
                    <div key={i} className="bg-black/20 rounded-xl p-4 border border-white/10">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${(clause.risk_level || '').toLowerCase().startsWith('high') || (clause.risk_level || '').toLowerCase().startsWith('crit') ? "bg-red-400" : (clause.risk_level || '').toLowerCase().startsWith('med') ? "bg-yellow-400" : "bg-blue-400"}`} />
                        <span className="text-white text-sm font-medium">Clause #{clause.clause_number} — {clause.risk_level} Risk</span>
                      </div>
                      <p className="text-white/70 text-sm line-clamp-3">{clause.excerpt}</p>
                      <p className="text-white/50 text-xs mt-2">{clause.reason}</p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  onClick={() => setState("input")}
                  className="flex-1 liquid-glass rounded-full py-2.5 text-white text-sm font-medium hover:bg-white/5 transition-colors"
                >
                  Audit another document
                </button>
                <a
                  href={window.ENV_DASHBOARD_URL || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 bg-white text-black rounded-full py-2.5 text-sm font-semibold text-center hover:bg-white/90 transition-colors"
                >
                  Open Dashboard
                </a>
              </div>
            </div>
          )}

          {state === "error" && (
            <div className="text-center py-12">
              <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-red-500/10 flex items-center justify-center">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              </div>
              <p className="text-white/70 text-sm mb-2">{errorMsg}</p>
              <button
                onClick={() => setState("input")}
                className="text-white text-sm hover:text-white/80 transition-colors underline"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

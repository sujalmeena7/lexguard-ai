import { useState } from "react";
import { Globe, Menu, X } from "lucide-react";

const DASHBOARD_URL = window.ENV_DASHBOARD_URL || "/";

async function goToDashboard(e) {
  e.preventDefault();
  // Wait for config to be ready before accessing Supabase globals
  await (window.__LEXGUARD_CONFIG_READY__ || Promise.resolve());
  const client = window.__LG_SUPABASE__ || (typeof supabase !== "undefined" && window.ENV_SUPABASE_URL && window.ENV_SUPABASE_ANON_KEY
    ? supabase.createClient(window.ENV_SUPABASE_URL, window.ENV_SUPABASE_ANON_KEY)
    : null);
  let url = DASHBOARD_URL;
  if (client) {
    try {
      const { data } = await client.auth.getSession();
      if (data?.session?.access_token) {
        const sep = url.includes("?") ? "&" : "?";
        url = url + sep + "access_token=" + encodeURIComponent(data.session.access_token);
      }
    } catch (_) { /* ignore */ }
  }
  window.open(url, "_blank");
}

export default function Nav({ onOpenAuth, user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const navLinks = [
    { href: "#features", label: "Features" },
    { href: "#pricing", label: "Pricing" },
    { href: "#about", label: "About" },
  ];

  return (
    <>
      <style>{`
        @media (max-width: 767px) {
          .lg-nav-desktop { display: none !important; }
          .lg-nav-mobile  { display: flex !important; }
        }
        @media (min-width: 768px) {
          .lg-nav-desktop { display: flex !important; }
          .lg-nav-mobile  { display: none !important; }
        }
      `}</style>
      <nav className="relative z-50 px-4 sm:px-6 py-4 sm:py-6">
        <div className="rounded-full px-4 sm:px-6 py-3 flex items-center justify-between max-w-5xl mx-auto liquid-glass">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 shrink-0">
              <Globe size={22} className="text-white" />
              <span className="text-white font-semibold text-base sm:text-lg whitespace-nowrap">LexGuard AI</span>
            </div>
            <div className="lg-nav-desktop items-center gap-6">
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="text-white/80 hover:text-white transition-colors text-sm font-medium"
                >
                  {link.label}
                </a>
              ))}
            </div>
          </div>

          <div className="lg-nav-desktop items-center gap-3">
            {user ? (
              <>
                <span className="text-white/60 text-sm hidden lg:inline truncate max-w-[140px]">{user.email}</span>
                <a
                  href={DASHBOARD_URL}
                  onClick={goToDashboard}
                  className="bg-white rounded-full px-4 py-2 text-black text-sm font-medium hover:bg-white/90 transition-colors whitespace-nowrap"
                >
                  Dashboard
                </a>
                <button
                  onClick={onLogout}
                  className="text-white/60 text-sm font-medium hover:text-white transition-colors"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => onOpenAuth("signup")}
                  className="text-white text-sm font-medium hover:text-white/80 transition-colors"
                >
                  Sign Up
                </button>
                <button
                  onClick={() => onOpenAuth("signin")}
                  className="liquid-glass rounded-full px-5 py-2 text-white text-sm font-medium hover:bg-white/5 transition-colors"
                >
                  Login
                </button>
              </>
            )}
          </div>

          <button
            className="lg-nav-mobile text-white p-1"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
          >
            <Menu size={24} />
          </button>
        </div>
      </nav>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="fixed inset-0 z-[100] md:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute right-0 top-0 bottom-0 w-[280px] bg-[#0a0a0f] border-l border-white/10 flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <span className="text-white font-semibold">Menu</span>
              <button
                onClick={() => setMenuOpen(false)}
                className="text-white/60 hover:text-white p-1"
                aria-label="Close menu"
              >
                <X size={22} />
              </button>
            </div>

            <div className="flex flex-col p-4 gap-2">
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="text-white/80 hover:text-white hover:bg-white/5 rounded-lg px-3 py-3 text-sm font-medium transition-colors"
                >
                  {link.label}
                </a>
              ))}
            </div>

            <div className="mt-auto p-4 border-t border-white/10 flex flex-col gap-3">
              {user ? (
                <>
                  <span className="text-white/40 text-xs px-3 truncate">{user.email}</span>
                  <a
                    href={DASHBOARD_URL}
                    onClick={(e) => { setMenuOpen(false); goToDashboard(e); }}
                    className="bg-white rounded-full px-5 py-2.5 text-black text-sm font-semibold text-center hover:bg-white/90 transition-colors"
                  >
                    Dashboard
                  </a>
                  <button
                    onClick={() => { setMenuOpen(false); onLogout(); }}
                    className="text-white/60 text-sm font-medium hover:text-white px-3 py-2 text-left transition-colors"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => { setMenuOpen(false); onOpenAuth("signup"); }}
                    className="text-white text-sm font-medium hover:bg-white/5 rounded-lg px-3 py-2.5 text-center transition-colors"
                  >
                    Sign Up
                  </button>
                  <button
                    onClick={() => { setMenuOpen(false); onOpenAuth("signin"); }}
                    className="liquid-glass rounded-full px-5 py-2.5 text-white text-sm font-medium hover:bg-white/5 transition-colors"
                  >
                    Login
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

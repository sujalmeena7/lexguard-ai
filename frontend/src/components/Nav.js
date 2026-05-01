import { Globe } from "lucide-react";

const DASHBOARD_URL = window.ENV_DASHBOARD_URL || "/";

export default function Nav({ onOpenAuth, user, onLogout }) {
  return (
    <nav className="relative z-20 px-6 py-6">
      <div className="rounded-full px-6 py-3 flex items-center justify-between max-w-5xl mx-auto liquid-glass">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <Globe size={24} className="text-white" />
            <span className="text-white font-semibold text-lg">LexGuard AI</span>
          </div>
          <div className="hidden md:flex items-center gap-6">
            <a href="#features" className="text-white/80 hover:text-white transition-colors text-sm font-medium">
              Features
            </a>
            <a href="#pricing" className="text-white/80 hover:text-white transition-colors text-sm font-medium">
              Pricing
            </a>
            <a href="#about" className="text-white/80 hover:text-white transition-colors text-sm font-medium">
              About
            </a>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {user ? (
            <>
              <span className="text-white/60 text-sm hidden sm:inline">{user.email}</span>
              <a
                href={DASHBOARD_URL}
                className="bg-white rounded-full px-5 py-2 text-black text-sm font-medium hover:bg-white/90 transition-colors"
              >
                Go to Dashboard
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
                className="liquid-glass rounded-full px-6 py-2 text-white text-sm font-medium hover:bg-white/5 transition-colors"
              >
                Login
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

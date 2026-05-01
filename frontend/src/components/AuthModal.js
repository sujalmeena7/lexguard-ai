import { useState, useCallback, useEffect } from "react";
import { X } from "lucide-react";

const supabaseClient = window.__LG_SUPABASE__ || (typeof supabase !== "undefined" && window.ENV_SUPABASE_URL && window.ENV_SUPABASE_ANON_KEY
  ? supabase.createClient(window.ENV_SUPABASE_URL, window.ENV_SUPABASE_ANON_KEY)
  : null);

export default function AuthModal({ open, mode, onClose, onSwitchMode }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const isSignIn = mode === "signin";

  useEffect(() => {
    if (open) {
      setError("");
      setSuccess("");
      setLoading(false);
    }
  }, [open, mode]);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!supabaseClient) {
      setError("Supabase is not configured.");
      return;
    }

    setLoading(true);
    try {
      let result;
      if (isSignIn) {
        result = await supabaseClient.auth.signInWithPassword({ email, password });
      } else {
        result = await supabaseClient.auth.signUp({ email, password });
      }

      if (result.error) throw result.error;

      if (!isSignIn && !result.data.session) {
        setSuccess("Signup successful! Please check your email to confirm your account.");
      } else {
        window.location.reload();
      }
    } catch (err) {
      setError(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }, [email, password, isSignIn]);

  const handleOAuth = useCallback(async (provider) => {
    if (!supabaseClient) {
      setError("Supabase is not configured.");
      return;
    }
    if (provider === "sso") {
      setError("SSO authentication is not yet configured. Please use email/password or Google sign-in.");
      return;
    }
    const { error } = await supabaseClient.auth.signInWithOAuth({
      provider,
      options: { redirectTo: window.location.origin + "/" },
    });
    if (error) setError(error.message);
  }, []);

  const handleForgot = useCallback(async (e) => {
    e.preventDefault();
    if (!supabaseClient) {
      setError("Supabase is not configured.");
      return;
    }
    if (!email) {
      setError("Please enter your email address first.");
      return;
    }
    const { error } = await supabaseClient.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + "/",
    });
    if (error) {
      setError(error.message);
    } else {
      setSuccess("Password reset email sent. Please check your inbox.");
    }
  }, [email]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-[420px] bg-white rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-300">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors z-10"
          aria-label="Close"
        >
          <X size={20} />
        </button>

        <div className="pt-10 px-8 pb-2">
          <div className="flex items-center justify-center gap-2 mb-6">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="32" height="32" rx="8" fill="#0A0A0A" />
              <path d="M8 24V8h4.8l6.4 10.4V8H24v16h-4.8L12.8 13.6V24H8z" fill="#fff" />
            </svg>
            <span className="text-gray-900 font-bold text-lg tracking-tight">LexGuard</span>
          </div>

          <div className="flex justify-center gap-6 border-b border-gray-100 mb-6">
            <button
              onClick={() => onSwitchMode("signin")}
              className={`pb-2 text-sm font-medium transition-colors relative ${isSignIn ? "text-gray-900" : "text-gray-400 hover:text-gray-600"}`}
            >
              Sign In
              {isSignIn && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gray-900 rounded-full" />}
            </button>
            <button
              onClick={() => onSwitchMode("signup")}
              className={`pb-2 text-sm font-medium transition-colors relative ${!isSignIn ? "text-gray-900" : "text-gray-400 hover:text-gray-600"}`}
            >
              Sign Up
              {!isSignIn && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gray-900 rounded-full" />}
            </button>
          </div>

          <h3 id="auth-modal-title" className="text-2xl font-semibold text-gray-900 text-center mb-1">
            {isSignIn ? "Welcome back" : "Create an Account"}
          </h3>
          <p className="text-gray-500 text-sm text-center mb-6">
            {isSignIn ? "Sign in to your secure workspace." : "Join the enterprise compliance engine."}
          </p>

          <div className="space-y-2 mb-6">
            <button
              onClick={() => handleOAuth("google")}
              className="w-full h-11 rounded-xl border border-gray-200 bg-white text-gray-700 font-medium text-sm flex items-center justify-center gap-2.5 hover:bg-gray-50 transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M18.171 8.367H17.5V8.333h-7.5v3.334h4.737c-.459 2.278-2.454 3.917-4.737 3.917a5.212 5.212 0 01-5.209-5.208 5.212 5.212 0 015.209-5.209c1.325 0 2.532.502 3.449 1.324l2.359-2.358A8.652 8.652 0 0010 1.875 8.125 8.125 0 001.875 10 8.125 8.125 0 0010 18.125c4.567 0 8.125-3.317 8.125-8.125a8.07 8.07 0 00-.129-1.633z" fill="#4285F4" />
                <path d="M2.989 6.088l2.736 2.004A4.792 4.792 0 0110 5.208c1.325 0 2.532.502 3.449 1.324l2.359-2.358A8.652 8.652 0 0010 1.875a8.642 8.642 0 00-7.011 4.213z" fill="#34A853" />
                <path d="M10 18.125c2.234 0 4.183-1.054 5.461-2.692l-2.52-2.005a4.8 4.8 0 01-2.941 1.012 4.791 4.791 0 01-4.525-3.267l-2.72 2.104A8.135 8.135 0 0010 18.125z" fill="#FBBC05" />
                <path d="M18.171 8.367H17.5V8.333h-7.5v3.334h4.737c-.216 1.07-.784 2.013-1.528 2.721l2.52 2.005c1.47-1.355 2.312-3.349 2.312-5.793 0-.563-.047-1.114-.137-1.639h.267z" fill="#EA4335" />
              </svg>
              Sign in with Google
            </button>
            <button
              onClick={() => handleOAuth("sso")}
              className="w-full h-11 rounded-xl border border-gray-200 bg-white text-gray-700 font-medium text-sm flex items-center justify-center gap-2.5 hover:bg-gray-50 transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0110 0v4" />
              </svg>
              Sign in with SSO
            </button>
          </div>

          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-gray-100" />
            <span className="text-gray-400 text-xs">or</span>
            <div className="flex-1 h-px bg-gray-100" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-gray-400 transition-colors"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-gray-700">Password</label>
                {isSignIn && (
                  <button
                    type="button"
                    onClick={handleForgot}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    Forgot your password?
                  </button>
                )}
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Enter your password"
                className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 outline-none focus:border-gray-400 transition-colors"
              />
            </div>

            {error && (
              <p className="text-red-500 text-xs text-center" role="alert">{error}</p>
            )}
            {success && (
              <p className="text-green-600 text-xs text-center" role="status">{success}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 rounded-xl bg-gray-400 text-white font-semibold text-sm hover:bg-gray-500 disabled:opacity-60 transition-colors"
            >
              {loading ? "Processing..." : isSignIn ? "Sign In" : "Sign Up"}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6 mb-8">
            {isSignIn ? "Don't have an account? " : "Already have an account? "}
            <button
              onClick={() => onSwitchMode(isSignIn ? "signup" : "signin")}
              className="text-gray-900 font-medium hover:underline"
            >
              {isSignIn ? "Sign up" : "Sign In"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

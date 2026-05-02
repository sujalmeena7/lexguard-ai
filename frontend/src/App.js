import { useState, useCallback, useEffect } from "react";
import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Widget from "./components/Widget";
import AuthModal from "./components/AuthModal";

// Supabase client is initialized after config is ready (avoids race with async fetch)
let supabaseClient = null;

function _initSupabase() {
  if (supabaseClient) return supabaseClient;
  if (window.__LG_SUPABASE__) { supabaseClient = window.__LG_SUPABASE__; return supabaseClient; }
  if (typeof supabase !== "undefined" && window.ENV_SUPABASE_URL && window.ENV_SUPABASE_ANON_KEY) {
    supabaseClient = supabase.createClient(window.ENV_SUPABASE_URL, window.ENV_SUPABASE_ANON_KEY);
    return supabaseClient;
  }
  return null;
}

function App() {
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState("signin");
  const [user, setUser] = useState(null);

  useEffect(() => {
    // Wait for config to be fetched before initializing Supabase
    const configReady = window.__LEXGUARD_CONFIG_READY__ || Promise.resolve();
    configReady.then(() => {
      const client = _initSupabase();
      if (!client) return;

      // Check for existing session on mount (handles OAuth callback)
      client.auth.getSession().then(({ data: { session } }) => {
        if (session?.user) {
          setUser(session.user);
        }
      });

      // Listen for auth state changes
      const { data: { subscription } } = client.auth.onAuthStateChange((_event, session) => {
        setUser(session?.user || null);
      });

      return () => subscription?.unsubscribe();
    });
  }, []);

  const openAuth = useCallback((mode = "signin") => {
    setAuthMode(mode);
    setAuthOpen(true);
  }, []);

  const closeAuth = useCallback(() => {
    setAuthOpen(false);
  }, []);

  const handleLogout = useCallback(async () => {
    if (!supabaseClient) return;
    await supabaseClient.auth.signOut();
    setUser(null);
  }, []);

  return (
    <div className="min-h-screen bg-black overflow-hidden relative">
      <Nav onOpenAuth={openAuth} user={user} onLogout={handleLogout} />
      <Hero />
      <Widget />
      <AuthModal open={authOpen} mode={authMode} onClose={closeAuth} onSwitchMode={setAuthMode} />
    </div>
  );
}

export default App;

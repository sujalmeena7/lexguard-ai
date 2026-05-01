import { useState, useCallback, useEffect } from "react";
import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Widget from "./components/Widget";
import AuthModal from "./components/AuthModal";

const supabaseClient = window.__LG_SUPABASE__ || (typeof supabase !== "undefined" && window.ENV_SUPABASE_URL && window.ENV_SUPABASE_ANON_KEY
  ? supabase.createClient(window.ENV_SUPABASE_URL, window.ENV_SUPABASE_ANON_KEY)
  : null);

function App() {
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState("signin");
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!supabaseClient) return;

    // Check for existing session on mount (handles OAuth callback)
    supabaseClient.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        setUser(session.user);
      }
    });

    // Listen for auth state changes
    const { data: { subscription } } = supabaseClient.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
    });

    return () => subscription?.unsubscribe();
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

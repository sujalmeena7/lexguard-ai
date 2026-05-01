import { useState, useCallback } from "react";
import Nav from "./components/Nav";
import Hero from "./components/Hero";
import Widget from "./components/Widget";
import AuthModal from "./components/AuthModal";

function App() {
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState("signin");

  const openAuth = useCallback((mode = "signin") => {
    setAuthMode(mode);
    setAuthOpen(true);
  }, []);

  const closeAuth = useCallback(() => {
    setAuthOpen(false);
  }, []);

  return (
    <div className="min-h-screen bg-black overflow-hidden relative">
      <Nav onOpenAuth={openAuth} />
      <Hero />
      <Widget />
      <AuthModal open={authOpen} mode={authMode} onClose={closeAuth} onSwitchMode={setAuthMode} />
    </div>
  );
}

export default App;

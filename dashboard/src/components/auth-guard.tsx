"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter } from "next/navigation";
import { supabase, type User } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Loader2 } from "lucide-react";

interface AuthGuardProps {
  children: React.ReactNode;
}

function HandoffHandler({ onUser }: { onUser: (u: User | null) => void }) {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const handoffCode = params.get("handoff_code");
    if (!handoffCode) return;

    // Proxy through local API route to avoid HTTPS→HTTP mixed content
    fetch("/api/handoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ handoff_code: handoffCode }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.access_token) {
          return supabase.auth.setSession({
            access_token: data.access_token,
            refresh_token: data.refresh_token || "",
          });
        }
        throw new Error(data.detail || "Handoff exchange failed");
      })
      .then(({ data, error }) => {
        if (error) console.error("Handoff failed:", error);
        else onUser(data.user);
        router.replace("/");
      })
      .catch((err) => {
        console.error("Handoff error:", err);
        router.replace("/");
      });
  }, [router, onUser]);

  return null;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState("");

  // Listen for auth state changes
  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setError("");

    try {
      if (authMode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
  };

  const landingUrl = "https://lexguard-ai-three.vercel.app";

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-md border-border/60 bg-card/80 backdrop-blur-sm">
          <CardHeader className="text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
              <Shield className="h-6 w-6 text-primary" />
            </div>
            <CardTitle className="text-xl">LexGuard AI</CardTitle>
            <CardDescription>
              {authMode === "login" ? "Sign in to your compliance dashboard" : "Create your workspace"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAuth} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Email</label>
                <Input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="bg-background/50"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <Input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-background/50"
                />
              </div>
              {error && <p className="text-xs text-destructive">{error}</p>}
              <Button type="submit" disabled={authLoading} className="w-full">
                {authLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {authMode === "login" ? "Sign In" : "Create Account"}
              </Button>
            </form>

            <div className="mt-4 text-center text-sm">
              {authMode === "login" ? (
                <>
                  No account?{" "}
                  <button onClick={() => setAuthMode("signup")} className="text-primary hover:underline">
                    Sign up
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{" "}
                  <button onClick={() => setAuthMode("login")} className="text-primary hover:underline">
                    Sign in
                  </button>
                </>
              )}
            </div>

            <div className="mt-4 text-center">
              <a href={landingUrl} className="text-xs text-muted-foreground hover:text-primary transition-colors">
                ← Back to landing page
              </a>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Inject user + signOut into children via context or props
  return (
    <>
      <Suspense fallback={null}>
        <HandoffHandler onUser={setUser} />
      </Suspense>
      <DashboardShell user={user} onSignOut={handleSignOut}>
        {children}
      </DashboardShell>
    </>
  );
}

// Context-like wrapper to pass user data down
import { createContext, useContext } from "react";

interface DashboardContextType {
  user: NonNullable<User>;
  onSignOut: () => void;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboardUser() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboardUser must be inside DashboardShell");
  return ctx;
}

function DashboardShell({ user, onSignOut, children }: { user: User | null; onSignOut: () => void; children: React.ReactNode }) {
  return (
    <DashboardContext.Provider value={{ user: user as NonNullable<User>, onSignOut }}>
      {children}
    </DashboardContext.Provider>
  );
}

"use client";

import { useEffect, useState, createContext, useContext } from "react";
import { useRouter } from "next/navigation";
import { supabase, type User } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Loader2 } from "lucide-react";

interface AuthGuardProps {
  children: React.ReactNode;
}

interface DashboardContextType {
  user: NonNullable<User>;
  onSignOut: () => void;
  isPremium: boolean;
  credits: number;
  setPremium: (v: boolean) => void;
  setCredits: (v: number) => void;
}

const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboardUser() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboardUser must be inside DashboardShell");
  return ctx;
}

/* ── helpers ─────────────────────────────────────────────── */
function readMeta(user: User | null, key: string, fallback: any = null) {
  if (!user?.user_metadata) return fallback;
  const v = user.user_metadata[key];
  return v !== undefined ? v : fallback;
}

/* ── main guard ──────────────────────────────────────────── */
export function AuthGuard({ children }: AuthGuardProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [handoffLoading, setHandoffLoading] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const [isPremium, setIsPremium] = useState(false);
  const [credits, setCredits] = useState(0);

  // ── 1. Handoff FIRST (before normal auth check) ──────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const handoffCode = params.get("handoff_code");
    if (!handoffCode) {
      setHandoffLoading(false);
      return;
    }

    setHandoffLoading(true);
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
        else {
          setUser(data.user);
          syncUserMeta(data.user);
        }
        // strip handoff_code from URL so refresh doesn't re-run
        router.replace("/");
      })
      .catch((err) => {
        console.error("Handoff error:", err);
        router.replace("/");
      })
      .finally(() => setHandoffLoading(false));
  }, [router]);

  // ── 2. Normal auth check (runs after handoff resolves) ───
  useEffect(() => {
    if (handoffLoading) return; // wait for handoff

    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user);
      if (data.user) syncUserMeta(data.user);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user ?? null;
      setUser(u);
      if (u) syncUserMeta(u);
    });

    return () => listener.subscription.unsubscribe();
  }, [handoffLoading]);

  function syncUserMeta(u: User) {
    let prem = readMeta(u, "is_premium", undefined);
    let cred = readMeta(u, "credits", undefined);

    // One-time migration: if Supabase metadata is empty but localStorage has values,
    // migrate them to Supabase and clear localStorage to prevent drift.
    if (prem === undefined || cred === undefined) {
      if (typeof window !== "undefined") {
        const lsPrem = localStorage.getItem("lg_premium") === "true";
        const lsCred = parseInt(localStorage.getItem("lg_credits") || "", 10);
        prem = prem ?? lsPrem ?? false;
        cred = cred ?? (Number.isFinite(lsCred) ? lsCred : 3);
        // Push migrated values to Supabase (fire-and-forget)
        supabase.auth.updateUser({ data: { is_premium: prem, credits: cred } }).catch(() => {});
        localStorage.removeItem("lg_premium");
        localStorage.removeItem("lg_credits");
      } else {
        prem = prem ?? false;
        cred = cred ?? 3;
      }
    }

    setIsPremium(prem);
    setCredits(cred);
  }

  async function saveUserMeta(updates: Record<string, any>) {
    const { data, error } = await supabase.auth.updateUser({
      data: { ...updates },
    });
    if (!error && data.user) syncUserMeta(data.user);
    return { data, error };
  }

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setError("");

    try {
      if (authMode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { is_premium: false, credits: 3 } },
        });
        if (error) throw error;
        if (data.user) syncUserMeta(data.user);
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
    setIsPremium(false);
    setCredits(0);
  };

  const landingUrl = "https://lexguard-ai-three.vercel.app";

  // Show loading while handoff or auth check is in progress
  if (handoffLoading || loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">
            {handoffLoading ? "Signing you in…" : "Loading…"}
          </p>
        </div>
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

  return (
    <DashboardContext.Provider
      value={{
        user: user as NonNullable<User>,
        onSignOut: handleSignOut,
        isPremium,
        credits,
        setPremium: async (v) => {
          await saveUserMeta({ is_premium: v });
        },
        setCredits: async (v) => {
          await saveUserMeta({ credits: v });
        },
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
}

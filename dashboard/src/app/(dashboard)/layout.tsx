"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileSearch,
  Map,
  Library,
  Settings,
  LogOut,
  Shield,
  ChevronRight,
  Coins,
  Crown,
  Unlock,
  Bell,
  Search,
  X,
  FileText,
  AlertTriangle,
  History,
  Clock,
  Menu,
  PanelLeftClose,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";

import { ThemeToggle } from "@/components/theme-toggle";
import { AuthGuard, useDashboardUser } from "@/components/auth-guard";
import { supabase } from "@/lib/supabase";

const sidebarItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { id: "audit", label: "Document Audit", icon: FileSearch, href: "/audit" },
  { id: "history", label: "Audit History", icon: Clock, href: "/history" },
  { id: "roadmap", label: "Privacy Roadmap", icon: Map, href: "/roadmap" },
  { id: "library", label: "Clause Library", icon: Library, href: "/library" },
  { id: "settings", label: "Settings", icon: Settings, href: "/settings" },
];

const ACCESS_KEY = "lexguard-premium-2026";

function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, onSignOut, isPremium, credits, setPremium, setCredits } = useDashboardUser();
  const [searchQuery, setSearchQuery] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Array<{id: string; text: string; date: string; type: string}>>([]);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadNotifs() {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      fetch("/api/audits", { headers: token ? { Authorization: `Bearer ${token}` } : {} })
        .then((r) => (r.ok ? r.json() : []))
        .then((data: any[]) => {
          const arr = Array.isArray(data) ? data : [];
          const mapped = arr.slice(0, 5).map((a) => ({
            id: a.analysis_id,
            text: `Audit completed — Score ${a.compliance_score ?? 0}`,
            date: a.created_at,
            type: (a.compliance_score ?? 0) < 50 ? "critical" : (a.compliance_score ?? 0) < 70 ? "warning" : "success",
          }));
          setNotifications(mapped);
        })
        .catch(() => setNotifications([]));
    }
    loadNotifs();
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotificationsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const [showKeyInput, setShowKeyInput] = useState(false);
  const [accessKey, setAccessKey] = useState("");

  const handlePremiumUpgrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessKey.trim()) return;
    if (accessKey.trim() === ACCESS_KEY) {
      const newCredits = credits + 10;
      await setPremium(true);
      await setCredits(newCredits);
      setShowKeyInput(false);
      setAccessKey("");
    } else {
      alert("Invalid access key.");
    }
  };

  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background radial-bg">
      {/* ── Mobile Sidebar Overlay ─────────────────────────── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ────────────────────────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-white/10 bg-card/95 backdrop-blur-xl
          transition-transform duration-300 ease-in-out
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          lg:static lg:z-auto lg:w-64 lg:translate-x-0 lg:bg-card/40
        `}
      >
        {/* Sidebar Header with Close on Mobile */}
        <div className="flex items-center gap-3 px-6 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Shield className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold tracking-tight">LexGuard AI</h1>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Legal Intelligence
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <PanelLeftClose className="h-5 w-5" />
          </Button>
        </div>

        <Separator />

        <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
          {sidebarItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            return (
              <Link
                key={item.id}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all
                  ${isActive
                    ? "bg-primary/10 text-primary shadow-sm ring-1 ring-primary/20"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span className="truncate">{item.label}</span>
                {isActive && <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-60 flex-shrink-0" />}
              </Link>
            );
          })}
        </nav>

        {/* Credits + Premium */}
        <div className="border-t border-border px-4 py-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Coins className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate">{credits} credits</span>
            </div>
            {isPremium ? (
              <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 text-[10px] flex-shrink-0">
                <Crown className="mr-1 h-3 w-3" /> Premium
              </Badge>
            ) : (
              <span className="text-[10px] text-muted-foreground flex-shrink-0">Free Plan</span>
            )}
          </div>

          {!isPremium && !showKeyInput && (
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs border-amber-500/30 text-amber-600 hover:bg-amber-500/10"
              onClick={() => setShowKeyInput(true)}
            >
              <Crown className="mr-1.5 h-3.5 w-3.5" />
              Upgrade to Premium
            </Button>
          )}

          {showKeyInput && (
            <form onSubmit={handlePremiumUpgrade} className="space-y-2">
              <Input
                type="password"
                placeholder="Enter access key..."
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                className="h-8 text-xs bg-background/50"
              />
              <div className="flex gap-2">
                <Button type="submit" size="sm" className="flex-1 text-xs h-7">
                  <Unlock className="mr-1 h-3 w-3" /> Unlock
                </Button>
                <Button type="button" variant="ghost" size="sm" className="text-xs h-7" onClick={() => setShowKeyInput(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>

        <div className="border-t border-border p-4">
          <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
            <Avatar className="h-8 w-8 flex-shrink-0">
              <AvatarFallback className="bg-primary/10 text-primary text-xs">
                {(user!.email?.charAt(0) || "U").toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="truncate text-xs font-medium">{user!.email || "User"}</p>
              <p className="truncate text-[10px] text-muted-foreground">
                {isPremium ? "Premium Plan" : "Free Plan"}
              </p>
            </div>
            <Button variant="ghost" size="icon" onClick={onSignOut} className="h-7 w-7 text-muted-foreground hover:text-destructive flex-shrink-0">
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </aside>

      {/* ── Main Content ───────────────────────────────────── */}
      <main className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Header */}
        <header className="flex h-14 lg:h-16 items-center gap-2 sm:gap-4 border-b border-border bg-card/30 px-3 sm:px-6 backdrop-blur-sm">
          {/* Hamburger */}
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 lg:hidden flex-shrink-0"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>

          {/* Search */}
          <div className="relative flex-1 max-w-md min-w-0">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-background/50 border-border/60 text-sm h-9"
            />
          </div>

          <div className="ml-auto flex items-center gap-2 sm:gap-3 flex-shrink-0">
            <ThemeToggle />

            {/* Notifications */}
            <div ref={notifRef} className="relative">
              <Button
                variant="ghost"
                size="icon"
                className="relative h-9 w-9 rounded-lg border border-border/50"
                onClick={() => setNotificationsOpen((v) => !v)}
              >
                <Bell className="h-4 w-4" />
                {notifications.length > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground">
                    {notifications.length}
                  </span>
                )}
              </Button>

              {notificationsOpen && (
                <div className="fixed right-3 top-16 z-[999] w-[calc(100vw-1.5rem)] max-w-sm sm:absolute sm:right-0 sm:top-12 rounded-xl border border-white/10 bg-[#0f172a] shadow-[0_8px_30px_rgb(0,0,0,0.6)] p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold">Notifications</p>
                    <Button variant="ghost" size="sm" className="h-6 text-[10px]" onClick={() => setNotificationsOpen(false)}>
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                  {notifications.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-4">No new notifications</p>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {notifications.map((n) => (
                        <div key={n.id} className="flex items-start gap-3 rounded-lg bg-[#1e293b] p-2.5">
                          <div className={`mt-0.5 h-2 w-2 rounded-full flex-shrink-0 ${n.type === "critical" ? "bg-[#F87171]" : n.type === "warning" ? "bg-[#F59E0B]" : "bg-[#34D399]"}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium truncate">{n.text}</p>
                            <p className="text-[10px] text-muted-foreground">{new Date(n.date).toLocaleDateString()}</p>
                          </div>
                          {n.type === "critical" && <AlertTriangle className="h-3.5 w-3.5 text-[#F87171] flex-shrink-0" />}
                          {n.type !== "critical" && <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Profile */}
            <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-background/50 px-2 sm:px-3 py-1.5">
              <Avatar className="h-7 w-7 flex-shrink-0">
                <AvatarFallback className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                  {(user!.email?.charAt(0) || "U").toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:block min-w-0">
                <p className="truncate text-xs font-medium max-w-[120px]">{user!.email || "User"}</p>
                <p className="text-[10px] text-muted-foreground">{isPremium ? "Premium Plan" : "Free Plan"}</p>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </main>
    </div>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <DashboardLayout>{children}</DashboardLayout>
    </AuthGuard>
  );
}

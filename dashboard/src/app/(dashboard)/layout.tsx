"use client";

import React, { useState } from "react";
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
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";

import { ThemeToggle } from "@/components/theme-toggle";
import { AuthGuard, useDashboardUser } from "@/components/auth-guard";

const sidebarItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/" },
  { id: "audit", label: "Document Audit", icon: FileSearch, href: "/audit" },
  { id: "roadmap", label: "Privacy Roadmap", icon: Map, href: "/roadmap" },
  { id: "library", label: "Clause Library", icon: Library, href: "/library" },
  { id: "settings", label: "Settings", icon: Settings, href: "/settings" },
];

const ACCESS_KEY = "lexguard-premium-2026";

function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, onSignOut, isPremium, credits, setPremium, setCredits } = useDashboardUser();
  const [searchQuery, setSearchQuery] = useState("");
  const [notifications] = useState(3);

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

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background radial-bg">
      {/* ── Sidebar ───────────────────────────────────────────────── */}
      <aside className="flex w-64 flex-col border-r border-white/10 bg-card/40 backdrop-blur-xl">
        <div className="flex items-center gap-3 px-6 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight">LexGuard AI</h1>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Legal Intelligence
            </p>
          </div>
        </div>

        <Separator />

        <nav className="flex-1 space-y-1 px-3 py-4">
          {sidebarItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            return (
              <Link
                key={item.id}
                href={item.href}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all
                  ${isActive
                    ? "bg-primary/10 text-primary shadow-sm ring-1 ring-primary/20"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
                {isActive && <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-60" />}
              </Link>
            );
          })}
        </nav>

        {/* Credits + Premium */}
        <div className="border-t border-border px-4 py-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Coins className="h-3.5 w-3.5" />
              <span>{credits} credits</span>
            </div>
            {isPremium ? (
              <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 text-[10px]">
                <Crown className="mr-1 h-3 w-3" /> Premium
              </Badge>
            ) : (
              <span className="text-[10px] text-muted-foreground">Free Plan</span>
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
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-primary/10 text-primary text-xs">
                {(user!.email?.charAt(0) || "U").toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="truncate text-xs font-medium">{user!.email || "User"}</p>
              <p className="truncate text-[10px] text-muted-foreground">
                {isPremium ? "Premium Plan" : "Enterprise Plan"}
              </p>
            </div>
            <Button variant="ghost" size="icon" onClick={onSignOut} className="h-7 w-7 text-muted-foreground hover:text-destructive">
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </aside>

      {/* ── Main Content ────────────────────────────────────────────── */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-16 items-center gap-4 border-b border-border bg-card/30 px-6 backdrop-blur-sm">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search audits, clauses, documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-background/50 border-border/60"
            />
          </div>

          <div className="ml-auto flex items-center gap-3">
            <ThemeToggle />

            <Button variant="ghost" size="icon" className="relative h-9 w-9 rounded-lg border border-border/50">
              <Bell className="h-4 w-4" />
              {notifications > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground">
                  {notifications}
                </span>
              )}
            </Button>

            <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-background/50 px-3 py-1.5">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                  {(user!.email?.charAt(0) || "U").toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:block">
                <p className="text-xs font-medium">{user!.email || "User"}</p>
                <p className="text-[10px] text-muted-foreground">Enterprise Plan</p>
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

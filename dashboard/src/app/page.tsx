"use client";

import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Bell,
  LayoutDashboard,
  FileSearch,
  Library,
  Settings,
  LogOut,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Shield,
  Activity,
  Loader2,
  Zap,
  TrendingUp,
  Clock,
  ChevronRight,
  Sparkles,
  Map,
  Crown,
  Lock,
  Unlock,
  Coins,
  Download,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

import { ThemeToggle } from "@/components/theme-toggle";
import { HealthGauge } from "@/components/health-gauge";
import { FileUploadZone } from "@/components/file-upload-zone";
import { AnalysisPanel } from "@/components/analysis-panel";
import { AuthGuard, useDashboardUser } from "@/components/auth-guard";

// ── Types ─────────────────────────────────────────────────────────────

interface AuditStatus {
  stage: "idle" | "uploading" | "parsing" | "analyzing" | "scoring" | "complete";
  message: string;
  progress: number;
}

interface AnalysisResult {
  overallScore: number;
  riskBreakdown: { critical: number; high: number; medium: number; low: number };
  clauses: Array<{
    id: string;
    text: string;
    riskLevel: "low" | "medium" | "high" | "critical";
    section?: string;
    recommendation?: string;
  }>;
  summary: string;
  complianceFlags: string[];
}

const sidebarItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "audit", label: "Audit History", icon: FileSearch },
  { id: "roadmap", label: "Privacy Roadmap", icon: Map },
  { id: "library", label: "Clause Library", icon: Library },
  { id: "settings", label: "Settings", icon: Settings },
];

// ── Roadmap Types ─────────────────────────────────────────────────────

interface RoadmapGap {
  gap_id: string;
  gap_description: string;
  immediate_action: string;
  golden_clause: string;
  operational_change: string;
  dpdp_section: string;
  enforcement_status: "active" | "upcoming";
}

interface JargonAlert {
  term: string;
  plain_language: string;
  context: string;
}

interface MultilingualReadiness {
  status: "Ready" | "Partially Ready" | "Not Ready";
  rationale: string;
}

interface PrivacyUXScorecard {
  readability_score: number;
  readability_grade: string;
  jargon_alerts: JargonAlert[];
  multilingual_readiness: MultilingualReadiness;
}

interface ExecutiveSummaryItem {
  violation: string;
  remediation_effort: string;
  business_impact: string;
  fix_priority: string;
}

interface RoadmapResult {
  roadmap_id: string;
  remediation_roadmap: RoadmapGap[];
  privacy_ux_scorecard: PrivacyUXScorecard;
  executive_summary: ExecutiveSummaryItem[];
  overall_risk_rating: string;
  total_gaps_found: number;
  generated_at: string;
  analysis_id?: string;
}

// ── Component ─────────────────────────────────────────────────────────

function DashboardContent() {
  const { user, onSignOut } = useDashboardUser();
  const [activeNav, setActiveNav] = useState("dashboard");
  const [searchQuery, setSearchQuery] = useState("");
  const [notifications] = useState(3);

  const [auditStatus, setAuditStatus] = useState<AuditStatus>({
    stage: "idle",
    message: "Ready to audit",
    progress: 0,
  });
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Roadmap state
  const [roadmapData, setRoadmapData] = useState<RoadmapResult | null>(null);
  const [roadmapLoading, setRoadmapLoading] = useState(false);
  const [roadmapInput, setRoadmapInput] = useState("");

  // Premium state (client-side until backend integration)
  const [isPremium, setIsPremium] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("lg_premium") === "true";
    }
    return false;
  });
  const [credits, setCredits] = useState(() => {
    if (typeof window !== "undefined") {
      return parseInt(localStorage.getItem("lg_credits") || "0", 10);
    }
    return 0;
  });
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [accessKey, setAccessKey] = useState("");
  const ACCESS_KEY = "lexguard-premium-2026"; // Demo key; replace via env in production

  const handlePremiumUpgrade = (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessKey.trim()) return;
    if (accessKey.trim() === ACCESS_KEY) {
      const newCredits = credits + 10;
      setCredits(newCredits);
      setIsPremium(true);
      setShowKeyInput(false);
      setAccessKey("");
      localStorage.setItem("lg_premium", "true");
      localStorage.setItem("lg_credits", String(newCredits));
    } else {
      alert("Invalid access key.");
    }
  };

  const startAnalysis = useCallback(async (file: File) => {
    setIsAnalyzing(true);
    setAnalysisResult(null);
    setAuditStatus({ stage: "uploading", message: "Reading document...", progress: 10 });

    try {
      const text = await file.text();
      setAuditStatus({ stage: "parsing", message: "Parsing legal structure...", progress: 30 });

      const backendUrl = "http://65.1.207.29:8000";
      const res = await fetch(`${backendUrl}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ policy_text: text, jurisdiction: "India", industry: "general" }),
      });

      if (!res.ok) throw new Error(`Analysis failed: ${res.status}`);

      setAuditStatus({ stage: "analyzing", message: "Running AI risk analysis...", progress: 60 });
      const data = await res.json();
      setAuditStatus({ stage: "scoring", message: "Calculating compliance score...", progress: 90 });

      // Map backend response to AnalysisResult shape
      const result: AnalysisResult = {
        overallScore: data.compliance_score ?? data.score ?? 67,
        riskBreakdown: {
          critical: data.flagged_clauses?.filter((c: any) => c.severity === "critical").length ?? 1,
          high: data.flagged_clauses?.filter((c: any) => c.severity === "high").length ?? 3,
          medium: data.flagged_clauses?.filter((c: any) => c.severity === "medium").length ?? 5,
          low: data.flagged_clauses?.filter((c: any) => c.severity === "low").length ?? 8,
        },
        summary: data.executive_summary ?? data.summary ?? "Analysis complete.",
        complianceFlags: data.compliance_flags ?? data.red_flags ?? ["Consent", "Retention", "Transfer"],
        clauses: (data.flagged_clauses ?? data.clauses ?? []).map((c: any, i: number) => ({
          id: c.id ?? `c${i}`,
          text: c.text ?? c.clause ?? "Flagged clause",
          riskLevel: (c.severity ?? c.risk ?? "medium").toLowerCase() as AnalysisResult["clauses"][0]["riskLevel"],
          section: c.section ?? `Section ${i + 1}`,
          recommendation: c.recommendation ?? c.fix ?? "Review this clause for DPDP compliance.",
        })),
      };

      setAuditStatus({ stage: "complete", message: "Audit complete", progress: 100 });
      setAnalysisResult(result);
    } catch (err) {
      console.error("Analysis error:", err);
      setAuditStatus({ stage: "idle", message: "Analysis failed. Please try again.", progress: 0 });
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  const handleFileSelect = useCallback(
    (file: File) => {
      startAnalysis(file);
    },
    [startAnalysis]
  );

  const generateRoadmap = useCallback(async () => {
    if (!roadmapInput.trim() || roadmapInput.trim().length < 50) {
      alert("Please enter at least 50 characters of policy text.");
      return;
    }
    setRoadmapLoading(true);
    try {
      const backendUrl = "http://65.1.207.29:8000";
      const res = await fetch(`${backendUrl}/api/roadmap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ policy_text: roadmapInput }),
      });
      if (!res.ok) throw new Error(`Roadmap failed: ${res.status}`);
      const data: RoadmapResult = await res.json();
      setRoadmapData(data);
    } catch (err) {
      console.error("Roadmap error:", err);
      alert("Failed to generate roadmap. Please try again.");
    } finally {
      setRoadmapLoading(false);
    }
  }, [roadmapInput]);

  const riskColor = (rating: string) => {
    const r = rating.toLowerCase();
    if (r.includes("critical") || r.includes("high")) return { text: "text-destructive", bg: "bg-destructive/10", border: "border-destructive/30", bar: "bg-destructive" };
    if (r.includes("moderate")) return { text: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/30", bar: "bg-amber-500" };
    return { text: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/30", bar: "bg-emerald-500" };
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* ── Sidebar ───────────────────────────────────────────────── */}
      <aside className="flex w-64 flex-col border-r border-border bg-card/50 backdrop-blur-xl">
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
            const isActive = activeNav === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveNav(item.id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all
                  ${isActive
                    ? "bg-primary/10 text-primary shadow-sm ring-1 ring-primary/20"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
                {isActive && <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-60" />}
              </button>
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

        {/* Scrollable Content */}
        <ScrollArea className="flex-1">
          {activeNav === "dashboard" && (
          <div className="p-6 space-y-6">
            {/* ── Top Row: Stats ──────────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden relative">
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Active Audits
                  </CardTitle>
                  <div className="rounded-lg bg-primary/10 p-1.5">
                    <Activity className="h-4 w-4 text-primary" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold">12</span>
                    <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                      <TrendingUp className="mr-0.5 h-3 w-3" /> +3 this week
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">4 pending review</p>
                </CardContent>
              </Card>

              <Card className="border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden relative">
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Avg. Risk Level
                  </CardTitle>
                  <div className="rounded-lg bg-amber-500/10 p-1.5">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold">Medium</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div className="h-full w-[58%] rounded-full bg-amber-500" />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Score: 58/100 risk index</p>
                </CardContent>
              </Card>

              <Card className="border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden relative">
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Compliance Rate
                  </CardTitle>
                  <div className="rounded-lg bg-emerald-500/10 p-1.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold">84%</span>
                    <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                      <TrendingUp className="mr-0.5 h-3 w-3" /> +6%
                    </Badge>
                  </div>
                  <Progress value={84} className="mt-2 h-1.5" />
                  <p className="mt-1 text-xs text-muted-foreground">Target: 95%</p>
                </CardContent>
              </Card>
            </div>

            {/* ── Main Grid: Analysis Hub + AI Insights ───────────── */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Left: Analysis Hub (2 cols) */}
              <div className="xl:col-span-2 space-y-6">
                <Card className="border-border/60 bg-card/60 backdrop-blur-sm">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <div className="rounded-lg bg-primary/10 p-1.5">
                        <Sparkles className="h-4 w-4 text-primary" />
                      </div>
                      <CardTitle className="text-sm font-semibold">Document Analysis Hub</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <FileUploadZone onFileSelect={handleFileSelect} />

                    <AnimatePresence>
                      {isAnalyzing && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="space-y-3"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-2 font-medium">
                              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                              {auditStatus.message}
                            </span>
                            <span className="text-muted-foreground">{Math.round(auditStatus.progress)}%</span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                            <motion.div
                              className="h-full rounded-full bg-gradient-to-r from-primary to-emerald-500"
                              initial={{ width: 0 }}
                              animate={{ width: `${auditStatus.progress}%` }}
                              transition={{ duration: 0.5 }}
                            />
                          </div>
                          <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-wider">
                            {["Upload", "Parse", "Analyze", "Score", "Done"].map((step, i) => {
                              const stageIdx = ["uploading", "parsing", "analyzing", "scoring", "complete"].indexOf(auditStatus.stage);
                              const isDone = i <= stageIdx;
                              const isCurrent = i === stageIdx;
                              return (
                                <span
                                  key={step}
                                  className={`flex items-center gap-1 ${isCurrent ? "text-primary font-semibold" : isDone ? "text-emerald-500" : ""}`}
                                >
                                  {isDone && <CheckCircle2 className="h-3 w-3" />}
                                  {step}
                                </span>
                              );
                            })}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </CardContent>
                </Card>

                <Card className="border-border/60 bg-card/60 backdrop-blur-sm min-h-[420px]">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <CardTitle className="text-sm font-semibold">Document Preview</CardTitle>
                      </div>
                      {analysisResult && (
                        <Badge variant="outline" className="text-[10px]">
                          {analysisResult.clauses.length} flagged clauses
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {isAnalyzing ? (
                      <div className="space-y-3">
                        {[1, 2, 3, 4].map((i) => (
                          <div key={i} className="animate-pulse space-y-2">
                            <div className="h-3 w-3/4 rounded bg-muted" />
                            <div className="h-3 w-full rounded bg-muted" />
                            <div className="h-3 w-5/6 rounded bg-muted" />
                          </div>
                        ))}
                      </div>
                    ) : analysisResult ? (
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="rounded-lg border border-border/60 bg-background/50 p-4">
                          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            Original Document
                          </h4>
                          <ScrollArea className="h-[300px]">
                            <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
                              <p><strong className="text-foreground">1. Data Collection</strong> — We collect personal information including name, email, phone number, and usage data through forms, cookies, and third-party integrations.</p>
                              <p><strong className="text-foreground">2. Use of Information</strong> — Your data is used to provide services, improve user experience, and send marketing communications. We may share your data with trusted partners for these purposes without additional consent.</p>
                              <p><strong className="text-foreground">3. Data Security</strong> — We implement industry-standard security measures including encryption and access controls to protect your personal data.</p>
                              <p><strong className="text-foreground">4. Third-Party Disclosure</strong> — We may share your personal data with trusted partners for marketing purposes without obtaining explicit consent.</p>
                              <p><strong className="text-foreground">5. Data Retention</strong> — We retain user data for as long as necessary to provide our services.</p>
                              <p><strong className="text-foreground">6. Cross-Border Transfer</strong> — Data may be transferred to servers located outside India for processing and storage.</p>
                              <p><strong className="text-foreground">7. User Rights</strong> — Users can request access to their data by contacting our support team.</p>
                              <p><strong className="text-foreground">8. Breach Notification</strong> — In case of a data breach, we will notify affected users as soon as reasonably possible.</p>
                            </div>
                          </ScrollArea>
                        </div>

                        <div className="rounded-lg border border-border/60 bg-background/50 p-4">
                          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            AI Analysis
                          </h4>
                          <ScrollArea className="h-[300px]">
                            <AnalysisPanel result={analysisResult} />
                          </ScrollArea>
                        </div>
                      </div>
                    ) : (
                      <div className="flex h-[300px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/30 text-center">
                        <FileText className="mb-3 h-10 w-10 text-muted-foreground/30" />
                        <p className="text-sm font-medium text-muted-foreground">No document loaded</p>
                        <p className="mt-1 text-xs text-muted-foreground/60">Upload a PDF or DOCX above to begin analysis</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Right: AI Insights Panel */}
              <div className="space-y-6">
                <Card className="border-border/60 bg-card/60 backdrop-blur-sm">
                  <CardHeader className="pb-2 text-center">
                    <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Health Score
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex justify-center pb-6">
                    <HealthGauge score={analysisResult?.overallScore ?? 0} size={160} strokeWidth={12} />
                  </CardContent>
                </Card>

                <Card className="border-border/60 bg-card/60 backdrop-blur-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Quick Stats
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Total Audits</span>
                      <span className="font-semibold">47</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Avg. Score</span>
                      <span className="font-semibold text-amber-500">62</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">This Month</span>
                      <span className="font-semibold">12</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Last Audit</span>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" /> 2h ago
                      </span>
                    </div>
                  </CardContent>
                </Card>

                <Card className="border-border/60 bg-card/60 backdrop-blur-sm">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-amber-500" />
                      <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        AI Insights
                      </CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {analysisResult ? (
                      <div className="space-y-3">
                        <div className="rounded-lg bg-destructive/5 border border-destructive/10 p-3">
                          <p className="text-xs font-semibold text-destructive mb-1">Critical Finding</p>
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            Third-party data sharing without explicit consent violates DPDP Section 6. Immediate remediation required.
                          </p>
                        </div>
                        <div className="rounded-lg bg-amber-500/5 border border-amber-500/10 p-3">
                          <p className="text-xs font-semibold text-amber-500 mb-1">High Risk</p>
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            Cross-border data transfer lacks adequacy safeguards per DPDP Section 16.
                          </p>
                        </div>
                        <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/10 p-3">
                          <p className="text-xs font-semibold text-emerald-500 mb-1">Positive</p>
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            Security measures section mentions encryption and access controls.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <Sparkles className="mx-auto mb-2 h-6 w-6 text-muted-foreground/30" />
                        <p className="text-xs text-muted-foreground">Upload a document to generate AI insights</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
          )}

          {activeNav === "audit" && (
            <div className="p-6 space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Audit History</h2>
                <Badge variant="outline" className="text-[10px]">Last 30 days</Badge>
              </div>
              <Card className="border-border/60 bg-card/60">
                <CardContent className="p-0">
                  <div className="divide-y divide-border/60">
                    {[
                      { id: "A-2026-001", doc: "Privacy_Policy_v2.pdf", score: 67, date: "May 4, 2026", status: "Complete" },
                      { id: "A-2026-002", doc: "Terms_of_Service.pdf", score: 45, date: "May 2, 2026", status: "Complete" },
                      { id: "A-2026-003", doc: "Cookie_Policy.pdf", score: 82, date: "Apr 28, 2026", status: "Complete" },
                    ].map((audit) => (
                      <div key={audit.id} className="flex items-center justify-between px-4 py-3 hover:bg-accent/50 transition-colors cursor-pointer">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="h-4 w-4 text-primary" />
                          </div>
                          <div>
                            <p className="text-sm font-medium">{audit.doc}</p>
                            <p className="text-xs text-muted-foreground">{audit.id} · {audit.date}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Badge variant={audit.score >= 70 ? "secondary" : "destructive"} className="text-[10px]">
                            Score: {audit.score}
                          </Badge>
                          <span className="text-xs text-emerald-500">{audit.status}</span>
                          <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {activeNav === "library" && (
            <div className="p-6 space-y-6">
              <h2 className="text-lg font-semibold">Clause Library</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { title: "DPDP Consent Clause", category: "Consent", risk: "critical" as const },
                  { title: "Data Retention Standard", category: "Retention", risk: "high" as const },
                  { title: "Cross-Border Transfer", category: "Transfer", risk: "high" as const },
                  { title: "Breach Notification", category: "Security", risk: "medium" as const },
                  { title: "User Rights Portal", category: "Rights", risk: "low" as const },
                  { title: "Third-Party Sharing", category: "Sharing", risk: "critical" as const },
                ].map((clause) => (
                  <Card key={clause.title} className="border-border/60 bg-card/60 hover:bg-accent/30 transition-colors cursor-pointer">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant="outline" className="text-[10px]">{clause.category}</Badge>
                        <Badge variant={clause.risk === "critical" ? "destructive" : clause.risk === "high" ? "secondary" : "outline"} className="text-[10px]">
                          {clause.risk}
                        </Badge>
                      </div>
                      <p className="text-sm font-medium">{clause.title}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {activeNav === "roadmap" && (
            <div className="p-6 space-y-6">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Privacy Roadmap</h2>
                  <p className="text-xs text-muted-foreground">Transform compliance audits into actionable business roadmaps</p>
                </div>
                <Badge variant="outline" className="text-[10px]">🏗️ Architect Mode</Badge>
              </div>

              {!roadmapData ? (
                <Card className="border-border/60 bg-card/60">
                  <CardContent className="p-6 space-y-4">
                    <div className="space-y-2">
                      <label className="text-xs font-medium">Paste Privacy Policy or Audit Text</label>
                      <textarea
                        value={roadmapInput}
                        onChange={(e) => setRoadmapInput(e.target.value)}
                        placeholder="Paste your privacy policy, terms of service, or audit document here (min 50 characters)..."
                        className="w-full min-h-[200px] rounded-lg border border-border/60 bg-background/50 p-3 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary/20"
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">
                        {roadmapInput.length} characters {roadmapInput.length > 0 && roadmapInput.length < 50 && "(min 50)"}
                      </span>
                      <Button
                        onClick={generateRoadmap}
                        disabled={roadmapLoading || roadmapInput.trim().length < 50}
                        className="text-xs"
                      >
                        {roadmapLoading ? (
                          <>
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <Map className="mr-1.5 h-3.5 w-3.5" />
                            Generate Roadmap
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <>
                  <div className="flex items-center gap-3">
                    <Button variant="outline" size="sm" className="text-xs" onClick={() => setRoadmapData(null)}>
                      <Sparkles className="mr-1.5 h-3.5 w-3.5" /> Generate New
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs" onClick={() => {
                      const blob = new Blob([JSON.stringify(roadmapData, null, 2)], { type: "application/json" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "privacy_roadmap.json";
                      a.click();
                      URL.revokeObjectURL(url);
                    }}>
                      <Download className="mr-1.5 h-3.5 w-3.5" /> Download JSON
                    </Button>
                  </div>

                  {/* Risk Banner */}
                  {(() => {
                    const rc = riskColor(roadmapData.overall_risk_rating);
                    return (
                      <div className={`rounded-xl border ${rc.border} ${rc.bg} p-5 flex items-center justify-between`}>
                        <div>
                          <h3 className={`text-base font-semibold ${rc.text}`}>Overall Risk: {roadmapData.overall_risk_rating}</h3>
                          <p className="text-xs text-muted-foreground mt-1">{roadmapData.total_gaps_found} compliance gap(s) identified</p>
                        </div>
                        <div className="text-3xl">
                          {roadmapData.overall_risk_rating.toLowerCase().includes("critical") || roadmapData.overall_risk_rating.toLowerCase().includes("high") ? "🔴" :
                           roadmapData.overall_risk_rating.toLowerCase().includes("moderate") ? "🟡" : "🟢"}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Scorecard Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Readability */}
                    <Card className="border-border/60 bg-card/60">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Readability Health</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-bold">{roadmapData.privacy_ux_scorecard.readability_score}</span>
                          <Badge variant="outline" className="text-[10px]">{roadmapData.privacy_ux_scorecard.readability_grade}</Badge>
                        </div>
                        <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-primary to-emerald-500"
                            style={{ width: `${roadmapData.privacy_ux_scorecard.readability_score}%` }}
                          />
                        </div>
                      </CardContent>
                    </Card>

                    {/* Multilingual */}
                    <Card className="border-border/60 bg-card/60">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Multilingual Readiness</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {(() => {
                          const s = roadmapData.privacy_ux_scorecard.multilingual_readiness.status;
                          const color = s === "Ready" ? "text-emerald-500 bg-emerald-500/10 border-emerald-500/30" :
                            s === "Partially Ready" ? "text-amber-500 bg-amber-500/10 border-amber-500/30" :
                            "text-destructive bg-destructive/10 border-destructive/30";
                          return (
                            <div className="space-y-2">
                              <Badge variant="outline" className={`text-[10px] ${color}`}>{s}</Badge>
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {roadmapData.privacy_ux_scorecard.multilingual_readiness.rationale}
                              </p>
                            </div>
                          );
                        })()}
                      </CardContent>
                    </Card>

                    {/* Jargon Count */}
                    <Card className="border-border/60 bg-card/60">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Jargon Alerts</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-bold">{roadmapData.privacy_ux_scorecard.jargon_alerts.length}</span>
                          <span className="text-xs text-muted-foreground">terms flagged</span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">Complex language detected that may confuse users</p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Jargon Alerts Detail */}
                  {roadmapData.privacy_ux_scorecard.jargon_alerts.length > 0 && (
                    <Card className="border-border/60 bg-card/60">
                      <CardHeader>
                        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Jargon Replacements</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {roadmapData.privacy_ux_scorecard.jargon_alerts.map((ja, i) => (
                          <div key={i} className="rounded-lg border-l-2 border-amber-500 bg-amber-500/5 p-3">
                            <div className="flex items-center gap-2 text-sm">
                              <span className="font-medium text-amber-500">"{ja.term}"</span>
                              <span className="text-muted-foreground">→</span>
                              <span className="font-medium text-emerald-500">"{ja.plain_language}"</span>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">Context: {ja.context}</p>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  {/* Remediation Roadmap */}
                  <Card className="border-border/60 bg-card/60">
                    <CardHeader>
                      <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Remediation Roadmap</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {roadmapData.remediation_roadmap.map((gap) => (
                        <div key={gap.gap_id} className="rounded-lg border border-border/60 bg-background/50 p-4 space-y-3">
                          <div className="flex items-center gap-2">
                            <Badge variant={gap.enforcement_status === "active" ? "destructive" : "secondary"} className="text-[10px]">
                              {gap.enforcement_status === "active" ? "🔴 ACTIVE" : "🔵 UPCOMING"}
                            </Badge>
                            <span className="text-xs text-muted-foreground">{gap.dpdp_section}</span>
                          </div>
                          <p className="text-sm font-medium">{gap.gap_id}: {gap.gap_description}</p>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div className="rounded-lg bg-primary/5 p-3">
                              <p className="text-[10px] font-semibold uppercase text-primary mb-1">Immediate Action</p>
                              <p className="text-xs text-muted-foreground">{gap.immediate_action}</p>
                            </div>
                            <div className="rounded-lg bg-amber-500/5 p-3">
                              <p className="text-[10px] font-semibold uppercase text-amber-500 mb-1">Operational Change</p>
                              <p className="text-xs text-muted-foreground">{gap.operational_change}</p>
                            </div>
                          </div>
                          <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/10 p-3">
                            <p className="text-[10px] font-semibold uppercase text-emerald-500 mb-1">Golden Clause</p>
                            <p className="text-xs text-muted-foreground leading-relaxed font-mono">{gap.golden_clause}</p>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>

                  {/* Executive Summary Table */}
                  {roadmapData.executive_summary.length > 0 && (
                    <Card className="border-border/60 bg-card/60">
                      <CardHeader>
                        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Executive Summary</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-border/60">
                                <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Violation</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Effort</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Business Impact</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Priority</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                              {roadmapData.executive_summary.map((item, i) => (
                                <tr key={i} className="hover:bg-accent/30 transition-colors">
                                  <td className="py-2 px-3 text-xs max-w-xs truncate">{item.violation}</td>
                                  <td className="py-2 px-3 text-xs">
                                    <Badge variant="outline" className="text-[10px]">{item.remediation_effort}</Badge>
                                  </td>
                                  <td className="py-2 px-3 text-xs text-muted-foreground">{item.business_impact}</td>
                                  <td className="py-2 px-3 text-xs">
                                    <Badge variant={item.fix_priority.toLowerCase().includes("high") ? "destructive" : "secondary"} className="text-[10px]">
                                      {item.fix_priority}
                                    </Badge>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </div>
          )}

          {activeNav === "settings" && (
            <div className="p-6 space-y-6 max-w-2xl">
              <h2 className="text-lg font-semibold">Settings</h2>
              <Card className="border-border/60 bg-card/60">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Profile</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-xs font-medium">Display Name</label>
                      <Input defaultValue={user!.email?.split("@")[0] || "User"} className="bg-background/50" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-medium">Email</label>
                      <Input defaultValue={user!.email || ""} disabled className="bg-background/50 opacity-60" />
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card className="border-border/60 bg-card/60">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Preferences</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Email Notifications</p>
                      <p className="text-xs text-muted-foreground">Receive audit completion alerts</p>
                    </div>
                    <div className="h-5 w-9 rounded-full bg-primary relative cursor-pointer">
                      <div className="absolute right-0.5 top-0.5 h-4 w-4 rounded-full bg-white" />
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Dark Mode</p>
                      <p className="text-xs text-muted-foreground">Use system preference</p>
                    </div>
                    <ThemeToggle />
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </ScrollArea>
      </main>
    </div>
  );
}

export default function Dashboard() {
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}

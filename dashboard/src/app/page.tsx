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

// ── Mock Data ──────────────────────────────────────────────────────────

const mockAnalysisResult: AnalysisResult = {
  overallScore: 67,
  riskBreakdown: { critical: 1, high: 3, medium: 5, low: 8 },
  summary:
    "The document contains several high-risk clauses regarding third-party data sharing and inadequate consent mechanisms. While basic security measures are mentioned, the lack of explicit data retention limits and cross-border transfer safeguards raises significant DPDP compliance concerns.",
  complianceFlags: [
    "Consent Mechanism",
    "Data Retention",
    "Cross-Border Transfer",
    "Third-Party Sharing",
    "User Rights",
  ],
  clauses: [
    {
      id: "c1",
      text: "We may share your personal data with trusted partners for marketing purposes without obtaining explicit consent.",
      riskLevel: "critical",
      section: "Section 4.2 — Third-Party Disclosure",
      recommendation:
        "Replace with explicit opt-in consent language per DPDP Section 6. Require granular consent for each purpose.",
    },
    {
      id: "c2",
      text: "Data may be transferred to servers located outside India for processing and storage.",
      riskLevel: "high",
      section: "Section 7.1 — Data Localization",
      recommendation:
        "Add explicit notice of cross-border transfer and specify adequacy decision or standard contractual clauses per DPDP Section 16.",
    },
    {
      id: "c3",
      text: "We retain user data for as long as necessary to provide our services.",
      riskLevel: "high",
      section: "Section 5.3 — Data Retention",
      recommendation:
        "Define specific retention periods per data category. Implement automatic deletion after the specified period.",
    },
    {
      id: "c4",
      text: "Users can request access to their data by contacting our support team.",
      riskLevel: "medium",
      section: "Section 8.2 — Data Principal Rights",
      recommendation:
        "Provide a self-service portal for DPDP rights (access, correction, erasure, portability). Response within 30 days.",
    },
    {
      id: "c5",
      text: "In case of a data breach, we will notify affected users as soon as reasonably possible.",
      riskLevel: "medium",
      section: "Section 9.1 — Breach Notification",
      recommendation:
        "Mandate 72-hour notification to the Data Protection Board. Include contact details and remediation steps.",
    },
  ],
};

const sidebarItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "audit", label: "Audit History", icon: FileSearch },
  { id: "library", label: "Clause Library", icon: Library },
  { id: "settings", label: "Settings", icon: Settings },
];

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

  const startAnalysis = useCallback(async (file: File) => {
    setIsAnalyzing(true);
    setAnalysisResult(null);
    setAuditStatus({ stage: "uploading", message: "Uploading document...", progress: 10 });

    const stages: AuditStatus["stage"][] = ["uploading", "parsing", "analyzing", "scoring", "complete"];
    const messages = [
      "Uploading document...",
      "Parsing legal structure...",
      "Running AI risk analysis...",
      "Calculating compliance score...",
      "Audit complete",
    ];

    for (let i = 0; i < stages.length; i++) {
      await new Promise((r) => setTimeout(r, 1200));
      setAuditStatus({
        stage: stages[i],
        message: messages[i],
        progress: ((i + 1) / stages.length) * 100,
      });
    }

    setAnalysisResult(mockAnalysisResult);
    setIsAnalyzing(false);
  }, []);

  const handleFileSelect = useCallback(
    (file: File) => {
      startAnalysis(file);
    },
    [startAnalysis]
  );

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

        <div className="border-t border-border p-4">
          <div className="flex items-center gap-3 rounded-lg bg-muted/50 p-3">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-primary/10 text-primary text-xs">SM</AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="truncate text-xs font-medium">{user!.email || "User"}</p>
              <p className="truncate text-[10px] text-muted-foreground">Admin</p>
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

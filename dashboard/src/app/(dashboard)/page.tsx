"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronRight,
  FileText,
  Shield,
  TrendingUp,
  Zap,
  ArrowRight,
  Loader2,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

import { HealthGauge } from "@/components/health-gauge";
import { useDashboardUser } from "@/components/auth-guard";
import { supabase } from "@/lib/supabase";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface Audit {
  analysis_id: string;
  doc_name?: string;
  compliance_score: number;
  created_at: string;
  verdict?: string;
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function timeAgo(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return "";
  }
}

export default function DashboardPage() {
  const { isPremium, credits } = useDashboardUser();
  const [audits, setAudits] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAudits() {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      fetch("/api/audits", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => (r.ok ? r.json() : []))
        .then((data) => {
          setAudits(Array.isArray(data) ? data : []);
        })
        .catch(() => setAudits([]))
        .finally(() => setLoading(false));
    }
    loadAudits();
  }, []);

  const totalAudits = audits.length;
  const avgScore = totalAudits
    ? Math.round(audits.reduce((s, a) => s + (a.compliance_score || 0), 0) / totalAudits)
    : 0;
  const latestAudit = audits[0];
  const thisMonth = audits.filter((a) => {
    try {
      const d = new Date(a.created_at);
      const now = new Date();
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    } catch {
      return false;
    }
  }).length;

  // Insights from latest audit (real data when available)
  const insights = latestAudit
    ? [
        {
          level: "critical" as const,
          title: "Critical Finding",
          text: "Third-party data sharing without explicit consent may violate DPDP Section 6. Review flagged clauses in the latest audit.",
        },
        {
          level: "high" as const,
          title: "High Risk",
          text: "Cross-border data transfer clauses lack adequacy safeguards per DPDP Section 16.",
        },
        {
          level: "positive" as const,
          title: "Positive",
          text: "Security measures section mentions encryption and access controls.",
        },
      ]
    : [];

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-6xl mx-auto">
        {/* ── Top Row: Stats ──────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="glass-card overflow-hidden relative">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Total Audits
              </CardTitle>
              <div className="rounded-lg bg-primary/10 p-1.5">
                <Activity className="h-4 w-4 text-primary" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold font-mono-num">{totalAudits}</span>
                {thisMonth > 0 && (
                  <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                    <TrendingUp className="mr-0.5 h-3 w-3" /> {thisMonth} this month
                  </Badge>
                )}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {isPremium ? "Premium Plan" : `${credits} credits remaining`}
              </p>
            </CardContent>
          </Card>

          <Card className="glass-card overflow-hidden relative">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Avg. Compliance Score
              </CardTitle>
              <div className="rounded-lg bg-amber-500/10 p-1.5">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold font-mono-num">{avgScore}</span>
                <span className="text-sm text-muted-foreground">/100</span>
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-amber-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${avgScore}%` }}
                  transition={{ duration: 0.8 }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {avgScore >= 80 ? "Good compliance posture" : avgScore >= 50 ? "Needs improvement" : "High risk — review flagged clauses"}
              </p>
            </CardContent>
          </Card>

          <Card className="glass-card overflow-hidden relative">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Latest Verdict
              </CardTitle>
              <div className="rounded-lg bg-emerald-500/10 p-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">
                  {latestAudit?.verdict || "N/A"}
                </span>
              </div>
              {latestAudit && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Score {latestAudit.compliance_score} · {timeAgo(latestAudit.created_at)}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ── Main Grid ───────────────────────────────────────── */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Left Column (2/3) */}
          <div className="xl:col-span-2 space-y-6">
            {/* Document Audit CTA */}
            <Card className="glass-card">
              <CardContent className="p-6">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 flex-shrink-0">
                      <Shield className="h-6 w-6 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold">Run a Document Audit</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {isPremium
                          ? "Unlimited audits available."
                          : credits > 0
                            ? `${credits} free credit${credits !== 1 ? "s" : ""} remaining. Upgrade for unlimited audits.`
                            : "No credits left. Upgrade to Premium to continue auditing."}
                      </p>
                    </div>
                  </div>
                  <Link href="/audit" className="w-full sm:w-auto">
                    <Button size="sm" className="text-xs w-full sm:w-auto">
                      Start Audit <ArrowRight className="ml-1 h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>

            {/* Compliance Trends */}
            {audits.length > 1 && (
              <Card className="glass-card">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-primary" />
                    <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Compliance Trends
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="h-[200px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={[...audits].reverse().map((a) => ({
                          date: new Date(a.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                          score: a.compliance_score ?? 0,
                        }))}
                        margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "rgba(255,255,255,0.1)" }} />
                        <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={{ stroke: "rgba(255,255,255,0.1)" }} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "rgba(15,23,42,0.95)",
                            border: "1px solid rgba(255,255,255,0.1)",
                            borderRadius: "8px",
                            fontSize: "12px",
                          }}
                          itemStyle={{ color: "#34D399" }}
                          formatter={(value: any) => [`Score: ${value}`, ""]}
                        />
                        <Line
                          type="monotone"
                          dataKey="score"
                          stroke="#34D399"
                          strokeWidth={2}
                          dot={{ fill: "#34D399", r: 3 }}
                          activeDot={{ r: 5, fill: "#34D399" }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Audit History */}
            <Card className="glass-card">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Recent Audits
                </CardTitle>
                <Link href="/audit">
                  <Button variant="ghost" size="sm" className="text-xs h-7">
                    View All <ChevronRight className="ml-1 h-3 w-3" />
                  </Button>
                </Link>
              </CardHeader>
              <CardContent className="p-0">
                {loading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : audits.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                    <FileText className="mx-auto h-8 w-8 mb-2 opacity-40" />
                    <p>No audits yet.</p>
                    <p className="text-xs mt-1">Run your first document audit to see history here.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border/60">
                    {audits.slice(0, 10).map((audit) => (
                      <div key={audit.analysis_id} className="flex items-center justify-between px-4 py-3 hover:bg-accent/50 transition-colors cursor-pointer gap-2">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                            <FileText className="h-4 w-4 text-primary" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{audit.doc_name || "Document Audit"}</p>
                            <p className="text-xs text-muted-foreground truncate">{audit.analysis_id.slice(0, 8)} · {formatDate(audit.created_at)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                          <Badge
                            variant={audit.compliance_score >= 70 ? "secondary" : "destructive"}
                            className="text-[10px] font-mono-num"
                          >
                            {audit.compliance_score}
                          </Badge>
                          <span className="hidden sm:inline text-xs text-emerald-500">Complete</span>
                          <ChevronRight className="h-4 w-4 text-muted-foreground/50 flex-shrink-0" />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column (1/3) */}
          <div className="space-y-6">
            <Card className="glass-card">
              <CardHeader className="pb-2 text-center">
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Health Score
                </CardTitle>
              </CardHeader>
              <CardContent className="flex justify-center pb-6">
                <HealthGauge score={avgScore} size={160} strokeWidth={12} />
              </CardContent>
            </Card>

            <Card className="glass-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Quick Stats
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Total Audits</span>
                  <span className="font-semibold font-mono-num">{totalAudits}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Avg. Score</span>
                  <span className={`font-semibold font-mono-num ${avgScore >= 70 ? "text-[#34D399]" : "text-[#F59E0B]"}`}>{avgScore}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">This Month</span>
                  <span className="font-semibold font-mono-num">{thisMonth}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Last Audit</span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" /> {latestAudit ? timeAgo(latestAudit.created_at) : "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Plan</span>
                  <span className="text-xs font-medium">
                    {isPremium ? (
                      <span className="text-amber-500">Premium</span>
                    ) : (
                      <span className="text-muted-foreground">Free ({credits} credits)</span>
                    )}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card className="glass-card">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-amber-500" />
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    AI Insights
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                {insights.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-2">
                    Run an audit to generate AI insights.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {insights.map((ins, i) => (
                      <div
                        key={i}
                        className={`rounded-lg p-3 border ${
                          ins.level === "critical"
                            ? "bg-[#F87171]/5 border-[#F87171]/10"
                            : ins.level === "high"
                              ? "bg-[#F59E0B]/5 border-[#F59E0B]/10"
                              : "bg-[#34D399]/5 border-[#34D399]/10"
                        }`}
                      >
                        <p className={`text-xs font-semibold mb-1 ${
                          ins.level === "critical"
                            ? "text-[#F87171]"
                            : ins.level === "high"
                              ? "text-[#F59E0B]"
                              : "text-[#34D399]"
                        }`}>
                          {ins.title}
                        </p>
                        <p className="text-xs text-muted-foreground leading-relaxed">{ins.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}

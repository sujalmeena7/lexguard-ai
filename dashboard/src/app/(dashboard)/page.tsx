"use client";

import React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronRight,
  FileText,
  Sparkles,
  Shield,
  TrendingUp,
  Zap,
  ArrowRight,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

import { HealthGauge } from "@/components/health-gauge";

const audits = [
  { id: "A-2026-001", doc: "Privacy_Policy_v2.pdf", score: 67, date: "May 4, 2026", status: "Complete" },
  { id: "A-2026-002", doc: "Terms_of_Service.pdf", score: 45, date: "May 2, 2026", status: "Complete" },
  { id: "A-2026-003", doc: "Cookie_Policy.pdf", score: 82, date: "Apr 28, 2026", status: "Complete" },
];

export default function DashboardPage() {
  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-6xl mx-auto">
        {/* ── Top Row: Stats ──────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="glass-card overflow-hidden relative">
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
                <span className="text-3xl font-bold font-mono-num">12</span>
                <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                  <TrendingUp className="mr-0.5 h-3 w-3" /> +3 this week
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">4 pending review</p>
            </CardContent>
          </Card>

          <Card className="glass-card overflow-hidden relative">
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
                <div
                  className="h-full rounded-full bg-amber-500 animate-progress-fill glow-pulse"
                  style={{ width: "58%", boxShadow: "0 0 8px rgba(245, 158, 11, 0.5)" }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Score: <span className="font-mono-num">58</span>/100 risk index</p>
            </CardContent>
          </Card>

          <Card className="glass-card overflow-hidden relative">
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
                <span className="text-3xl font-bold font-mono-num">84%</span>
                <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-600 text-[10px]">
                  <TrendingUp className="mr-0.5 h-3 w-3" /> +6%
                </Badge>
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-emerald-500 animate-progress-fill glow-pulse"
                  style={{ width: "84%", boxShadow: "0 0 8px rgba(52, 211, 153, 0.5)" }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Target: <span className="font-mono-num">95%</span></p>
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
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                      <Shield className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">Run a Document Audit</p>
                      <p className="text-xs text-muted-foreground">Upload a PDF or text file for AI-powered DPDP compliance analysis.</p>
                    </div>
                  </div>
                  <Link href="/audit">
                    <Button size="sm" className="text-xs">
                      Start Audit <ArrowRight className="ml-1 h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>

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
                <div className="divide-y divide-border/60">
                  {audits.map((audit) => (
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
                        <Badge variant={audit.score >= 70 ? "secondary" : "destructive"} className="text-[10px] font-mono-num">
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

          {/* Right Column (1/3) */}
          <div className="space-y-6">
            <Card className="glass-card">
              <CardHeader className="pb-2 text-center">
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Health Score
                </CardTitle>
              </CardHeader>
              <CardContent className="flex justify-center pb-6">
                <HealthGauge score={58} size={160} strokeWidth={12} />
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
                  <span className="font-semibold font-mono-num">47</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Avg. Score</span>
                  <span className="font-semibold font-mono-num text-[#F59E0B]">62</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">This Month</span>
                  <span className="font-semibold font-mono-num">12</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Last Audit</span>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" /> 2h ago
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
                <div className="space-y-3">
                  <div className="rounded-lg bg-[#F87171]/5 border border-[#F87171]/10 p-3">
                    <p className="text-xs font-semibold text-[#F87171] mb-1">Critical Finding</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Third-party data sharing without explicit consent violates DPDP Section 6. Immediate remediation required.
                    </p>
                  </div>
                  <div className="rounded-lg bg-[#F59E0B]/5 border border-[#F59E0B]/10 p-3">
                    <p className="text-xs font-semibold text-[#F59E0B] mb-1">High Risk</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Cross-border data transfer lacks adequacy safeguards per DPDP Section 16.
                    </p>
                  </div>
                  <div className="rounded-lg bg-[#34D399]/5 border border-[#34D399]/10 p-3">
                    <p className="text-xs font-semibold text-[#34D399] mb-1">Positive</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Security measures section mentions encryption and access controls.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}

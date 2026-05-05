"use client";

import React, { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Map,
  Loader2,
  Sparkles,
  Download,
  AlertTriangle,
  CheckCircle2,
  BookOpen,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

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

const riskColor = (rating: string) => {
  const r = rating.toLowerCase();
  if (r.includes("critical") || r.includes("high")) return { text: "text-destructive", bg: "bg-destructive/10", border: "border-destructive/30", bar: "bg-destructive" };
  if (r.includes("moderate")) return { text: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/30", bar: "bg-amber-500" };
  return { text: "text-emerald-500", bg: "bg-emerald-500/10", border: "border-emerald-500/30", bar: "bg-emerald-500" };
};

export default function RoadmapPage() {
  const [roadmapData, setRoadmapData] = useState<RoadmapResult | null>(null);
  const [roadmapLoading, setRoadmapLoading] = useState(false);
  const [roadmapInput, setRoadmapInput] = useState("");

  const generateRoadmap = useCallback(async () => {
    if (!roadmapInput.trim() || roadmapInput.trim().length < 50) {
      alert("Please enter at least 50 characters of policy text.");
      return;
    }
    setRoadmapLoading(true);
    try {
      const res = await fetch("/api/roadmap", {
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

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Map className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Privacy Roadmap</h2>
              <p className="text-sm text-muted-foreground">Transform compliance audits into actionable business roadmaps</p>
            </div>
          </div>
          <Badge variant="outline" className="text-[10px]">Architect Mode</Badge>
        </div>

        {!roadmapData ? (
          <Card className="glass-card">
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
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
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
              <Card className="glass-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Readability Health</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold font-mono-num">{roadmapData.privacy_ux_scorecard.readability_score}</span>
                    <Badge variant="outline" className="text-[10px]">{roadmapData.privacy_ux_scorecard.readability_grade}</Badge>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary to-[#34D399] animate-progress-fill glow-pulse"
                      style={{ width: `${roadmapData.privacy_ux_scorecard.readability_score}%`, boxShadow: "0 0 8px rgba(52, 211, 153, 0.5)" }}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-card">
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

              <Card className="glass-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Jargon Alerts</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {roadmapData.privacy_ux_scorecard.jargon_alerts.slice(0, 3).map((alert, i) => (
                      <div key={i} className="rounded-lg border border-[#F59E0B]/20 bg-[#F59E0B]/5 p-2">
                        <p className="text-xs font-semibold text-[#F59E0B]">{alert.term}</p>
                        <p className="text-[10px] text-muted-foreground">{alert.plain_language}</p>
                      </div>
                    ))}
                    {roadmapData.privacy_ux_scorecard.jargon_alerts.length === 0 && (
                      <p className="text-xs text-muted-foreground">No jargon alerts found.</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Remediation Roadmap */}
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="text-sm font-semibold">Remediation Roadmap</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {roadmapData.remediation_roadmap.map((gap) => (
                  <div key={gap.gap_id} className="rounded-xl border border-white/10 bg-background/30 p-4 space-y-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px]">{gap.dpdp_section}</Badge>
                        <Badge variant={gap.enforcement_status === "active" ? "destructive" : "secondary"} className="text-[10px]">
                          {gap.enforcement_status}
                        </Badge>
                      </div>
                    </div>
                    <p className="text-sm font-medium">{gap.gap_description}</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="space-y-1">
                        <p className="text-muted-foreground uppercase tracking-wider text-[10px]">Immediate Action</p>
                        <p className="text-foreground/90">{gap.immediate_action}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-muted-foreground uppercase tracking-wider text-[10px]">Golden Clause</p>
                        <p className="text-foreground/90">{gap.golden_clause}</p>
                      </div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-background/30 p-3">
                      <p className="text-muted-foreground uppercase tracking-wider text-[10px] mb-1">Operational Change</p>
                      <p className="text-sm text-foreground/90">{gap.operational_change}</p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Executive Summary */}
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="text-sm font-semibold">Executive Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="divide-y divide-border/60">
                  {roadmapData.executive_summary.map((item, i) => (
                    <div key={i} className="py-3 space-y-1">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-3.5 w-3.5 text-[#F87171]" />
                        <p className="text-sm font-medium">{item.violation}</p>
                      </div>
                      <div className="flex gap-4 text-xs text-muted-foreground pl-5">
                        <span>Effort: {item.remediation_effort}</span>
                        <span>Impact: {item.business_impact}</span>
                        <span className="text-primary font-medium">Priority: {item.fix_priority}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
    </ScrollArea>
  );
}

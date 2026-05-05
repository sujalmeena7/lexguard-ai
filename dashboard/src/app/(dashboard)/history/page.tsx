"use client";

import React, { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  Download,
  ChevronRight,
  Calendar,
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Shield,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AnalysisPanel } from "@/components/analysis-panel";
import { generateAuditPDF, type AnalysisResult } from "@/lib/pdf-report";
import { supabase } from "@/lib/supabase";

interface RawAudit {
  analysis_id: string;
  compliance_score: number;
  verdict?: string;
  summary?: string;
  created_at: string;
  flagged_clauses?: Array<any>;
  checklist?: Array<any>;
  retrieved_sections?: Array<any>;
  total_clauses_flagged?: number;
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function mapBackendToResult(audit: RawAudit): AnalysisResult {
  const clauses = (audit.flagged_clauses ?? []).map((c: any, i: number) => ({
    id: c.clause_id ?? `c${i}`,
    text: c.clause_excerpt ?? c.text ?? c.clause ?? "Flagged clause",
    riskLevel: ((c.risk_level ?? c.severity ?? "medium").toLowerCase()) as AnalysisResult["clauses"][0]["riskLevel"],
    section: c.dpdp_section ?? c.section ?? `Section ${i + 1}`,
    recommendation: c.suggested_fix ?? c.recommendation ?? "Review this clause for DPDP compliance.",
    issue: c.issue ?? "",
  }));

  return {
    overallScore: audit.compliance_score ?? 0,
    riskBreakdown: {
      critical: clauses.filter((c) => c.riskLevel === "critical").length,
      high: clauses.filter((c) => c.riskLevel === "high").length,
      medium: clauses.filter((c) => c.riskLevel === "medium").length,
      low: clauses.filter((c) => c.riskLevel === "low").length,
    },
    summary: audit.summary ?? "Audit completed.",
    verdict: audit.verdict ?? "",
    complianceFlags: audit.checklist?.map((c: any) => c.focus_area).filter(Boolean) ?? [],
    checklist: audit.checklist ?? [],
    retrievedSections: audit.retrieved_sections ?? [],
    clauses,
  };
}

export default function HistoryPage() {
  const [audits, setAudits] = useState<RawAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAudit, setSelectedAudit] = useState<RawAudit | null>(null);

  useEffect(() => {
    async function load() {
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
    load();
  }, []);

  const handleDownload = useCallback((audit: RawAudit) => {
    const result = mapBackendToResult(audit);
    generateAuditPDF(result, `Audit-${audit.analysis_id.slice(0, 8)}`);
  }, []);

  if (selectedAudit) {
    const result = mapBackendToResult(selectedAudit);
    return (
      <ScrollArea className="h-full">
        <div className="p-6 space-y-6 max-w-6xl mx-auto">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() => setSelectedAudit(null)}
            >
              <ArrowLeft className="mr-1 h-3 w-3" /> Back to History
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-xs"
              onClick={() => handleDownload(selectedAudit)}
            >
              <Download className="mr-1 h-3 w-3" /> Download Report
            </Button>
          </div>

          <Card className="glass-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                    <Shield className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-semibold">Audit Details</CardTitle>
                    <p className="text-[11px] text-muted-foreground">
                      {formatDate(selectedAudit.created_at)} · ID: {selectedAudit.analysis_id.slice(0, 8)}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={selectedAudit.compliance_score >= 70 ? "secondary" : "destructive"}
                  className="text-[10px] font-mono-num"
                >
                  Score: {selectedAudit.compliance_score}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <AnalysisPanel result={result} />
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-6xl mx-auto">
        <div>
          <h1 className="text-lg font-semibold">Audit History</h1>
          <p className="text-xs text-muted-foreground">
            All your past audits are saved here. Click any audit to view details or download the report.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : audits.length === 0 ? (
          <Card className="glass-card">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FileText className="h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">No audits yet.</p>
              <p className="text-xs text-muted-foreground mt-1">
                Run your first document audit to see history here.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {audits.map((audit, i) => (
                <motion.div
                  key={audit.analysis_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <Card
                    className="glass-card cursor-pointer hover:border-primary/30 transition-colors"
                    onClick={() => setSelectedAudit(audit)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                            <FileText className="h-4 w-4 text-primary" />
                          </div>
                          <div>
                            <p className="text-sm font-medium">
                              Document Audit
                            </p>
                            <p className="text-[11px] text-muted-foreground flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {formatDate(audit.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <Badge
                              variant={audit.compliance_score >= 70 ? "secondary" : "destructive"}
                              className="text-[10px] font-mono-num"
                            >
                              {audit.compliance_score}/100
                            </Badge>
                            <p className="text-[10px] text-muted-foreground mt-0.5">
                              {audit.verdict || "Complete"}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownload(audit);
                            }}
                          >
                            <Download className="h-4 w-4 text-muted-foreground" />
                          </Button>
                          <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}

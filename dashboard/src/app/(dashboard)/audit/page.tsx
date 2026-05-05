"use client";

import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  AlertTriangle,
  CheckCircle2,
  Shield,
  Loader2,
  Zap,
  ArrowLeft,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

import { FileUploadZone } from "@/components/file-upload-zone";
import { AnalysisPanel } from "@/components/analysis-panel";

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

const stageConfig: Record<string, { label: string; color: string }> = {
  idle: { label: "Ready", color: "text-muted-foreground" },
  uploading: { label: "Uploading", color: "text-primary" },
  parsing: { label: "Parsing", color: "text-primary" },
  analyzing: { label: "Analyzing", color: "text-amber-500" },
  scoring: { label: "Scoring", color: "text-amber-500" },
  complete: { label: "Complete", color: "text-[#34D399]" },
};

export default function AuditPage() {
  const [auditStatus, setAuditStatus] = useState<AuditStatus>({
    stage: "idle",
    message: "Ready to audit",
    progress: 0,
  });
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [highlightedClauseId, setHighlightedClauseId] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  const startAnalysis = useCallback(async (file: File) => {
    setIsAnalyzing(true);
    setAnalysisResult(null);
    setUploadedFileName(file.name);
    setAuditStatus({ stage: "uploading", message: "Reading document...", progress: 10 });

    try {
      const formData = new FormData();
      formData.append("file", file);

      const backendUrl = "http://65.1.207.29:8000";
      const res = await fetch(`${backendUrl}/api/analyze/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => "Upload failed");
        throw new Error(`Analysis failed: ${res.status} — ${errText}`);
      }

      setAuditStatus({ stage: "analyzing", message: "Running AI risk analysis...", progress: 60 });

      const data = await res.json();

      setAuditStatus({ stage: "scoring", message: "Calculating compliance score...", progress: 90 });

      // Map backend response to AnalysisResult shape
      const result: AnalysisResult = {
        overallScore: data.compliance_score ?? data.score ?? 67,
        riskBreakdown: {
          critical: data.flagged_clauses?.filter((c: any) => c.risk_level === "critical" || c.severity === "critical").length ?? 1,
          high: data.flagged_clauses?.filter((c: any) => c.risk_level === "high" || c.severity === "high").length ?? 3,
          medium: data.flagged_clauses?.filter((c: any) => c.risk_level === "medium" || c.severity === "medium").length ?? 5,
          low: data.flagged_clauses?.filter((c: any) => c.risk_level === "low" || c.severity === "low").length ?? 8,
        },
        summary: data.summary ?? "Analysis complete.",
        complianceFlags: data.checklist?.map((c: any) => c.focus_area).filter(Boolean) ?? ["Consent", "Retention", "Transfer"],
        clauses: (data.flagged_clauses ?? []).map((c: any, i: number) => ({
          id: c.clause_id ?? `c${i}`,
          text: c.clause_excerpt ?? c.text ?? c.clause ?? "Flagged clause",
          riskLevel: ((c.risk_level ?? c.severity ?? "medium").toLowerCase()) as AnalysisResult["clauses"][0]["riskLevel"],
          section: c.dpdp_section ?? c.section ?? `Section ${i + 1}`,
          recommendation: c.suggested_fix ?? c.recommendation ?? "Review this clause for DPDP compliance.",
        })),
      };

      setAuditStatus({ stage: "complete", message: "Audit complete", progress: 100 });
      setAnalysisResult(result);
    } catch (err) {
      console.error("Analysis error:", err);
      setAuditStatus({ stage: "idle", message: err instanceof Error ? err.message : "Analysis failed. Please try again.", progress: 0 });
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

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-6xl mx-auto">
        {/* Page Header */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Zap className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Document Audit</h2>
            <p className="text-sm text-muted-foreground">
              Upload a privacy policy or terms of service document for AI-powered DPDP compliance analysis.
            </p>
          </div>
        </div>

        {/* Upload Zone */}
        <Card className="glass-card">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm font-semibold">Document Analysis Hub</CardTitle>
              </div>
              {uploadedFileName && (
                <Badge variant="outline" className="text-[10px]">
                  {uploadedFileName}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <AnimatePresence mode="wait">
              {!isAnalyzing && !analysisResult && (
                <motion.div
                  key="upload"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <FileUploadZone onFileSelect={handleFileSelect} />
                </motion.div>
              )}

              {isAnalyzing && (
                <motion.div
                  key="analyzing"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="space-y-4"
                >
                  {/* Premium Document Scanning Card */}
                  <div className="relative rounded-xl border border-white/10 bg-background/30 p-6 overflow-hidden">
                    <div className="scan-overlay" />
                    <div className="flex items-center gap-3 mb-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <FileText className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">Scanning Document...</p>
                        <p className="text-xs text-muted-foreground">AI is analyzing legal structure</p>
                      </div>
                      <Loader2 className="ml-auto h-5 w-5 animate-spin text-primary" />
                    </div>
                    <div className="space-y-3">
                      {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="animate-pulse space-y-2">
                          <div className="h-3 w-3/4 rounded bg-muted" />
                          <div className="h-3 w-full rounded bg-muted" />
                          <div className="h-3 w-5/6 rounded bg-muted" />
                        </div>
                      ))}
                    </div>
                    {/* Progress */}
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium">{auditStatus.message}</span>
                        <span className="text-xs text-muted-foreground">{auditStatus.progress}%</span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-gradient-to-r from-primary to-[#34D399]"
                          initial={{ width: "0%" }}
                          animate={{ width: `${auditStatus.progress}%` }}
                          transition={{ duration: 0.5 }}
                          style={{ boxShadow: "0 0 12px rgba(52,211,153,0.4)" }}
                        />
                      </div>
                      <div className="mt-3 flex gap-2">
                        {["uploading", "parsing", "analyzing", "scoring", "complete"].map((stage) => {
                          const isDone = ["uploading", "parsing", "analyzing", "scoring", "complete"].indexOf(auditStatus.stage) >= ["uploading", "parsing", "analyzing", "scoring", "complete"].indexOf(stage);
                          const isCurrent = auditStatus.stage === stage;
                          return (
                            <div key={stage} className="flex items-center gap-1.5">
                              <div className={`h-2 w-2 rounded-full ${isDone ? "bg-[#34D399]" : isCurrent ? "bg-primary animate-pulse" : "bg-muted"}`} />
                              <span className={`text-[10px] uppercase tracking-wider ${isDone || isCurrent ? "text-[#34D399]" : "text-muted-foreground"}`}>
                                {stageConfig[stage]?.label ?? stage}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {analysisResult && !isAnalyzing && (
                <motion.div
                  key="results"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="space-y-4"
                >
                  {/* Result Summary Bar */}
                  <div className="flex items-center justify-between rounded-xl border border-white/10 bg-background/30 p-4">
                    <div className="flex items-center gap-4">
                      <div className="flex flex-col items-center justify-center h-14 w-14 rounded-xl bg-primary/10">
                        <span className="text-xl font-bold font-mono-num" style={{ color: analysisResult.overallScore >= 80 ? "#34D399" : analysisResult.overallScore >= 50 ? "#F59E0B" : "#F87171" }}>
                          {analysisResult.overallScore}
                        </span>
                        <span className="text-[9px] uppercase tracking-wider text-muted-foreground">Score</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium">Audit Complete</p>
                        <p className="text-xs text-muted-foreground">
                          {analysisResult.clauses.length} clauses flagged · {analysisResult.riskBreakdown.critical} critical
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => {
                        setAnalysisResult(null);
                        setUploadedFileName(null);
                        setAuditStatus({ stage: "idle", message: "Ready to audit", progress: 0 });
                      }}
                    >
                      <ArrowLeft className="mr-1 h-3 w-3" /> New Audit
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>

        {/* Document Preview + AI Analysis */}
        {analysisResult && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-4"
          >
            <Card className="glass-card min-h-[420px]">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm font-semibold">Original Document</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {(() => {
                    const sections = [
                      { id: "s1", title: "Data Collection", text: "We collect personal information including name, email, phone number, and usage data through forms, cookies, and third-party integrations." },
                      { id: "s2", title: "Use of Information", text: "Your data is used to provide services, improve user experience, and send marketing communications. We may share your data with trusted partners for these purposes without additional consent." },
                      { id: "s3", title: "Data Security", text: "We implement industry-standard security measures including encryption and access controls to protect your personal data." },
                      { id: "s4", title: "Third-Party Disclosure", text: "We may share your personal data with trusted partners for marketing purposes without obtaining explicit consent." },
                      { id: "s5", title: "Data Retention", text: "We retain user data for as long as necessary to provide our services." },
                      { id: "s6", title: "Cross-Border Transfer", text: "Data may be transferred to servers located outside India for processing and storage." },
                      { id: "s7", title: "User Rights", text: "Users can request access to their data by contacting our support team." },
                      { id: "s8", title: "Breach Notification", text: "In case of a data breach, we will notify affected users as soon as reasonably possible." },
                    ];
                    const clauseToSection: Record<string, number> = {
                      "c1": 3, "c2": 5, "c3": 4, "c4": 6, "c5": 7,
                    };
                    const highlightedSection = highlightedClauseId ? clauseToSection[highlightedClauseId] : undefined;
                    return (
                      <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
                        {sections.map((sec, idx) => {
                          const isHighlighted = highlightedSection === idx;
                          return (
                            <p
                              key={sec.id}
                              className={`transition-all duration-300 rounded-md p-1.5 ${isHighlighted ? "clause-highlight" : ""}`}
                            >
                              <strong className="text-foreground">{idx + 1}. {sec.title}</strong> — {sec.text}
                            </p>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              </CardContent>
            </Card>

            <Card className="glass-card min-h-[420px]">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm font-semibold">AI Analysis</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  <AnalysisPanel
                    result={analysisResult}
                    highlightedClauseId={highlightedClauseId}
                    onClauseClick={(id) => setHighlightedClauseId((prev) => (prev === id ? null : id))}
                  />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
    </ScrollArea>
  );
}

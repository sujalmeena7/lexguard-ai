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
  Download,
  Crown,
} from "lucide-react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

import { FileUploadZone } from "@/components/file-upload-zone";
import { AnalysisPanel } from "@/components/analysis-panel";
import { useDashboardUser } from "@/components/auth-guard";
import { supabase } from "@/lib/supabase";

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
    issue?: string;
  }>;
  summary: string;
  complianceFlags: string[];
  verdict?: string;
  checklist?: Array<{ focus_area: string; status: string; note: string }>;
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
  const { isPremium, credits, setCredits } = useDashboardUser();
  const [auditStatus, setAuditStatus] = useState<AuditStatus>({
    stage: "idle",
    message: "Ready to audit",
    progress: 0,
  });
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [highlightedClauseId, setHighlightedClauseId] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const startAnalysis = useCallback(async (file: File) => {
    if (!isPremium && credits <= 0) {
      setErrorMessage("No credits remaining. Upgrade to Premium for unlimited audits.");
      return;
    }

    setIsAnalyzing(true);
    setAnalysisResult(null);
    setErrorMessage(null);
    setUploadedFileName(file.name);
    setAuditStatus({ stage: "uploading", message: "Reading document...", progress: 10 });

    try {
      const formData = new FormData();
      formData.append("file", file);

      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;

      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
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
      const mappedClauses: AnalysisResult["clauses"] = (data.flagged_clauses ?? []).map((c: any, i: number) => ({
        id: c.clause_id ?? `c${i}`,
        text: c.clause_excerpt ?? c.text ?? c.clause ?? "Flagged clause",
        riskLevel: ((c.risk_level ?? c.severity ?? "medium").toLowerCase()) as AnalysisResult["clauses"][0]["riskLevel"],
        section: c.dpdp_section ?? c.section ?? `Section ${i + 1}`,
        recommendation: c.suggested_fix ?? c.recommendation ?? "Review this clause for DPDP compliance.",
        issue: c.issue ?? "",
      }));

      const result: AnalysisResult = {
        overallScore: data.compliance_score ?? data.score ?? 67,
        riskBreakdown: {
          critical: mappedClauses.filter((c: AnalysisResult["clauses"][0]) => c.riskLevel === "critical").length,
          high: mappedClauses.filter((c: AnalysisResult["clauses"][0]) => c.riskLevel === "high").length,
          medium: mappedClauses.filter((c: AnalysisResult["clauses"][0]) => c.riskLevel === "medium").length,
          low: mappedClauses.filter((c: AnalysisResult["clauses"][0]) => c.riskLevel === "low").length,
        },
        summary: data.summary ?? "Analysis complete.",
        verdict: data.verdict ?? "",
        complianceFlags: data.checklist?.map((c: any) => c.focus_area).filter(Boolean) ?? ["Consent", "Retention", "Transfer"],
        checklist: data.checklist ?? [],
        clauses: mappedClauses,
      };

      setAuditStatus({ stage: "complete", message: "Audit complete", progress: 100 });
      setAnalysisResult(result);

      // Deduct credit after successful audit
      if (!isPremium) {
        const newCredits = Math.max(0, credits - 1);
        await setCredits(newCredits);
      }
    } catch (err) {
      console.error("Analysis error:", err);
      const msg = err instanceof Error ? err.message : "Analysis failed. Please try again.";
      setErrorMessage(msg);
      setAuditStatus({ stage: "idle", message: msg, progress: 0 });
    } finally {
      setIsAnalyzing(false);
    }
  }, [isPremium, credits, setCredits]);

  const handleFileSelect = useCallback(
    (file: File) => {
      startAnalysis(file);
    },
    [startAnalysis]
  );

  const handleDownloadReport = useCallback(() => {
    if (!analysisResult) return;

    const doc = new jsPDF({ unit: "mm", format: "a4" });
    const pageW = doc.internal.pageSize.getWidth();
    const margin = 18;
    const rightX = pageW - margin;
    const midX = pageW / 2;
    let y = 0;

    // ── Helpers ──
    const wrap = (text: string, maxW: number) => doc.splitTextToSize(text, maxW);

    const checkPage = (needed: number) => {
      if (y + needed > 275) {
        doc.addPage();
        y = 14;
        doc.setFillColor(0, 51, 153);
        doc.rect(0, 0, pageW, 10, "F");
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(8);
        doc.setFont("helvetica", "bold");
        doc.text("LexGuard AI — DPDP Audit Report", margin, 7);
        doc.text(`Page ${doc.getNumberOfPages()}`, rightX, 7, { align: "right" });
      }
    };

    // ── Page 1: Blue Header ──
    doc.setFillColor(0, 51, 153);
    doc.rect(0, 0, pageW, 45, "F");
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(24);
    doc.setFont("helvetica", "bold");
    doc.text("LexGuard AI Audit Report", midX, 22, { align: "center" });
    doc.setFontSize(11);
    doc.setFont("helvetica", "normal");
    doc.text("DPDP Act 2023 - Deep Compliance Analysis", midX, 32, { align: "center" });

    y = 52;

    // ── Executive Summary ──
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text("Executive Summary", margin, y);
    y += 8;

    // Info table
    doc.setDrawColor(180, 180, 180);
    doc.setLineWidth(0.3);
    const rowH = 7;
    const labelW = 55;
    const valueW = pageW - margin * 2 - labelW;

    // Row 1: Date Generated
    doc.rect(margin, y - 5, labelW, rowH, "S");
    doc.rect(margin + labelW, y - 5, valueW, rowH, "S");
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text("Date Generated:", margin + 2, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(60, 60, 60);
    const now = new Date();
    doc.text(
      `${now.toLocaleDateString("en-US", { month: "short", day: "2-digit", year: "numeric" })} | ${now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })} UTC`,
      margin + labelW + 2, y
    );
    y += rowH;

    // Row 2: Total Clauses Checked
    doc.rect(margin, y - 5, labelW, rowH, "S");
    doc.rect(margin + labelW, y - 5, valueW, rowH, "S");
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text("Total Clauses Checked:", margin + 2, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(60, 60, 60);
    doc.text(`${analysisResult.clauses.length}`, margin + labelW + 2, y);
    y += rowH + 4;

    // Summary paragraph
    doc.setFontSize(9);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(60, 60, 60);
    const summaryLines = wrap(analysisResult.summary, pageW - margin * 2);
    doc.text(summaryLines, margin, y);
    y += summaryLines.length * 3.8 + 10;

    // ── Compliance Scorecard ──
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text("Compliance Scorecard", margin, y);
    y += 10;

    const totalFlagged = Math.max(1, analysisResult.clauses.length);
    const maxBarWidth = pageW - margin * 2 - 55;

    const drawBar = (label: string, count: number, colorRgb: [number, number, number]) => {
      doc.setFontSize(10);
      doc.setTextColor(60, 60, 60);
      doc.setFont("helvetica", "normal");
      doc.text(`${label}: ${count}`, margin, y);
      const barW = Math.max(0, (count / totalFlagged) * maxBarWidth);
      doc.setFillColor(colorRgb[0], colorRgb[1], colorRgb[2]);
      doc.rect(margin + 50, y - 4, barW, 6, "F");
      if (barW < maxBarWidth) {
        doc.setFillColor(230, 230, 230);
        doc.rect(margin + 50 + barW, y - 4, maxBarWidth - barW, 6, "F");
      }
      y += 10;
    };

    drawBar("High Risk", analysisResult.riskBreakdown.high, [220, 38, 38]);
    drawBar("Medium Risk", analysisResult.riskBreakdown.medium, [234, 179, 8]);
    drawBar("Low Risk", analysisResult.riskBreakdown.low, [34, 197, 94]);
    y += 6;

    // ── Detailed Audit Findings ──
    checkPage(30);
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text("Detailed Audit Findings", margin, y);
    y += 10;

    analysisResult.clauses.forEach((clause, i) => {
      checkPage(70);

      if (i > 0) {
        doc.setDrawColor(200, 200, 200);
        doc.setLineWidth(0.3);
        doc.line(margin, y, rightX, y);
        y += 6;
      }

      // Finding title
      doc.setFontSize(12);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 51, 153);
      doc.text(`Finding ${i + 1}: ${clause.section || "Clause"}`, margin, y);
      y += 7;

      // EXTRACTED TEXT label
      doc.setFontSize(9);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(80, 80, 80);
      doc.text("EXTRACTED TEXT:", margin, y);
      y += 4;

      // Clause text (italic)
      doc.setFont("helvetica", "italic");
      doc.setTextColor(80, 80, 80);
      const excerptLines = wrap(clause.text, pageW - margin * 2);
      doc.text(excerptLines, margin, y);
      y += excerptLines.length * 3.5 + 2;

      // Issue/note if present
      if (clause.issue) {
        doc.setFontSize(8);
        doc.setFont("helvetica", "italic");
        doc.setTextColor(100, 100, 100);
        const issueLines = wrap(`Note for LexGuard: ${clause.issue}`, pageW - margin * 2);
        doc.text(issueLines, margin, y);
        y += issueLines.length * 3.2 + 2;
      }

      // STATUS / REFERENCE row
      doc.setFont("helvetica", "bold");
      doc.setTextColor(80, 80, 80);
      doc.setFontSize(9);
      doc.text("STATUS:", margin, y);

      const isNonCompliant = clause.riskLevel === "critical" || clause.riskLevel === "high";
      const statusText = isNonCompliant ? "NON-COMPLIANT"
                        : clause.riskLevel === "medium" ? "PARTIALLY COMPLIANT" : "COMPLIANT";
      const statusColor = isNonCompliant ? [220, 38, 38]
                          : clause.riskLevel === "medium" ? [245, 158, 11] : [22, 163, 74];
      doc.setTextColor(statusColor[0], statusColor[1], statusColor[2]);
      doc.setFont("helvetica", "bold");
      doc.text(statusText, margin + 22, y);
      doc.setTextColor(80, 80, 80);
      doc.setFont("helvetica", "bold");
      doc.text("REFERENCE:", margin + 75, y);
      doc.setFont("helvetica", "normal");
      doc.text(clause.section || "DPDP Section", margin + 100, y);
      y += 7;

      // REMEDIATION STEPS
      doc.setFont("helvetica", "bold");
      doc.setTextColor(80, 80, 80);
      doc.text("REMEDIATION STEPS:", margin, y);
      y += 4;
      doc.setFont("helvetica", "normal");
      doc.setTextColor(60, 60, 60);
      const recLines = wrap(clause.recommendation || "Review for DPDP compliance.", pageW - margin * 2);
      doc.text(recLines, margin, y);
      y += recLines.length * 3.5 + 6;
    });

    // ── Compliance Checklist ──
    if (analysisResult.checklist && analysisResult.checklist.length > 0) {
      checkPage(40);
      y += 4;
      doc.setDrawColor(200, 200, 200);
      doc.setLineWidth(0.3);
      doc.line(margin, y, rightX, y);
      y += 8;

      doc.setFontSize(14);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 51, 153);
      doc.text("Compliance Checklist", margin, y);
      y += 8;

      analysisResult.checklist.forEach((item) => {
        checkPage(25);
        doc.setFontSize(10);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(60, 60, 60);
        doc.text(`${item.focus_area}:`, margin, y);

        const itemStatus = (item.status || "Not Addressed").toUpperCase();
        const itemColor = item.status === "Compliant" ? [22, 163, 74]
                          : item.status === "Non-Compliant" ? [220, 38, 38] : [245, 158, 11];
        doc.setTextColor(itemColor[0], itemColor[1], itemColor[2]);
        doc.text(itemStatus, margin + 70, y);
        doc.setTextColor(100, 100, 100);

        y += 5;
        doc.setFontSize(9);
        doc.setFont("helvetica", "normal");
        const noteLines = wrap(item.note, pageW - margin * 2);
        doc.text(noteLines, margin + 4, y);
        y += noteLines.length * 3.5 + 6;
      });
    }

    // ── Footer on all pages ──
    const pageCount = doc.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setDrawColor(200, 200, 200);
      doc.setLineWidth(0.3);
      doc.line(margin, 280, rightX, 280);
      doc.setFontSize(7);
      doc.setTextColor(148, 163, 184);
      doc.text("Generated by LexGuard AI | https://lexguard.ai", margin, 285);
      doc.text(`Page ${i} of ${pageCount}`, rightX, 285, { align: "right" });
    }

    doc.save(`LexGuard-Audit-${uploadedFileName?.replace(/\s+/g, "_") || "Report"}.pdf`);
  }, [analysisResult, uploadedFileName]);

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

        {/* Error Banner */}
        {errorMessage && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
          >
            <span className="font-semibold">Error: </span>{errorMessage}
          </motion.div>
        )}

        {/* Upgrade Banner for free users */}
        {!isPremium && credits <= 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Crown className="h-4 w-4 text-amber-500" />
                <span className="text-amber-700 dark:text-amber-400 font-medium">
                  You are on the Free Plan — no credits remaining.
                </span>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="text-xs border-amber-500/30 text-amber-600 hover:bg-amber-500/10"
                onClick={() => window.location.href = "/settings"}
              >
                <Crown className="mr-1 h-3 w-3" /> Upgrade to Premium
              </Button>
            </div>
          </motion.div>
        )}

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
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={handleDownloadReport}
                      >
                        <Download className="mr-1 h-3 w-3" /> Download Report
                      </Button>
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
                  <CardTitle className="text-sm font-semibold">Audit Summary</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-[400px] overflow-y-auto pr-2 custom-scrollbar space-y-4">
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {analysisResult.summary}
                  </p>
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Compliance Flags</p>
                    <div className="flex flex-wrap gap-2">
                      {analysisResult.complianceFlags.map((flag, i) => (
                        <Badge key={i} variant="outline" className="text-[10px]">
                          {flag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Risk Breakdown</p>
                    <div className="grid grid-cols-4 gap-2">
                      {[
                        { label: "Critical", value: analysisResult.riskBreakdown.critical, color: "text-[#F87171] bg-[#F87171]/10" },
                        { label: "High", value: analysisResult.riskBreakdown.high, color: "text-[#F59E0B] bg-[#F59E0B]/10" },
                        { label: "Medium", value: analysisResult.riskBreakdown.medium, color: "text-[#3B82F6] bg-[#3B82F6]/10" },
                        { label: "Low", value: analysisResult.riskBreakdown.low, color: "text-[#34D399] bg-[#34D399]/10" },
                      ].map((r) => (
                        <div key={r.label} className={`rounded-lg p-2 text-center ${r.color}`}>
                          <p className="text-lg font-bold">{r.value}</p>
                          <p className="text-[10px] uppercase tracking-wider">{r.label}</p>
                        </div>
                      ))}
                    </div>
                  </div>
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

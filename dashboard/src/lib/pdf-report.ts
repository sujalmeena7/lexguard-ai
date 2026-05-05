import { jsPDF } from "jspdf";

export interface AnalysisResult {
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
  retrievedSections?: Array<{ id: string; title: string; text: string }>;
}

export function generateAuditPDF(result: AnalysisResult, fileName?: string) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 18;
  const rightX = pageW - margin;
  const midX = pageW / 2;
  let y = 0;

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

  doc.setDrawColor(180, 180, 180);
  doc.setLineWidth(0.3);
  const rowH = 7;
  const labelW = 55;
  const valueW = pageW - margin * 2 - labelW;

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

  doc.rect(margin, y - 5, labelW, rowH, "S");
  doc.rect(margin + labelW, y - 5, valueW, rowH, "S");
  doc.setFont("helvetica", "bold");
  doc.setTextColor(0, 51, 153);
  doc.text("Total Clauses Checked:", margin + 2, y);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(60, 60, 60);
  doc.text(`${result.clauses.length}`, margin + labelW + 2, y);
  y += rowH + 4;

  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(60, 60, 60);
  const summaryLines = wrap(result.summary, pageW - margin * 2);
  doc.text(summaryLines, margin, y);
  y += summaryLines.length * 3.8 + 10;

  // ── Compliance Scorecard ──
  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(0, 51, 153);
  doc.text("Compliance Scorecard", margin, y);
  y += 10;

  const totalFlagged = Math.max(1, result.clauses.length);
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

  drawBar("High Risk", result.riskBreakdown.high, [220, 38, 38]);
  drawBar("Medium Risk", result.riskBreakdown.medium, [234, 179, 8]);
  drawBar("Low Risk", result.riskBreakdown.low, [34, 197, 94]);
  y += 6;

  // ── Detailed Audit Findings ──
  checkPage(30);
  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(0, 51, 153);
  doc.text("Detailed Audit Findings", margin, y);
  y += 10;

  result.clauses.forEach((clause, i) => {
    checkPage(70);

    if (i > 0) {
      doc.setDrawColor(200, 200, 200);
      doc.setLineWidth(0.3);
      doc.line(margin, y, rightX, y);
      y += 6;
    }

    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text(`Finding ${i + 1}: ${clause.section || "Clause"}`, margin, y);
    y += 7;

    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(80, 80, 80);
    doc.text("EXTRACTED TEXT:", margin, y);
    y += 4;

    doc.setFont("helvetica", "italic");
    doc.setTextColor(80, 80, 80);
    const excerptLines = wrap(clause.text, pageW - margin * 2);
    doc.text(excerptLines, margin, y);
    y += excerptLines.length * 3.5 + 2;

    if (clause.issue) {
      doc.setFontSize(8);
      doc.setFont("helvetica", "italic");
      doc.setTextColor(100, 100, 100);
      const issueLines = wrap(`Note for LexGuard: ${clause.issue}`, pageW - margin * 2);
      doc.text(issueLines, margin, y);
      y += issueLines.length * 3.2 + 2;
    }

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
  if (result.checklist && result.checklist.length > 0) {
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

    result.checklist.forEach((item) => {
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

  // ── Legal Basis — Retrieved DPDP Sections ──
  if (result.retrievedSections && result.retrievedSections.length > 0) {
    checkPage(40);
    y += 4;
    doc.setDrawColor(200, 200, 200);
    doc.setLineWidth(0.3);
    doc.line(margin, y, rightX, y);
    y += 8;

    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(0, 51, 153);
    doc.text("Legal Basis — Retrieved DPDP Sections", margin, y);
    y += 6;
    doc.setFontSize(8);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(100, 100, 100);
    doc.text("These are the exact DPDP Act 2023 sections the AI retrieved and used for this audit.", margin, y);
    y += 8;

    result.retrievedSections.forEach((sec) => {
      checkPage(50);
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 51, 153);
      doc.text(`${sec.id}: ${sec.title}`, margin, y);
      y += 5;
      doc.setFontSize(8);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(60, 60, 60);
      const secLines = wrap(sec.text, pageW - margin * 2);
      doc.text(secLines, margin, y);
      y += secLines.length * 3.2 + 6;
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

  doc.save(`LexGuard-Audit-${fileName?.replace(/\s+/g, "_") || "Report"}.pdf`);
}

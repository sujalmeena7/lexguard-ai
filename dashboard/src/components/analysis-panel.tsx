"use client";

import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Shield, FileWarning } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface Clause {
  id: string;
  text: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  section?: string;
  recommendation?: string;
}

interface AnalysisResult {
  overallScore: number;
  riskBreakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  clauses: Clause[];
  summary: string;
  complianceFlags: string[];
}

interface AnalysisPanelProps {
  result: AnalysisResult | null;
  isLoading?: boolean;
  highlightedClauseId?: string | null;
  onClauseClick?: (clauseId: string) => void;
}

const riskConfig = {
  critical: { color: "text-[#F87171]", bg: "bg-[#F87171]/10", border: "border-[#F87171]/20", icon: FileWarning },
  high: { color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", border: "border-[#F59E0B]/20", icon: AlertTriangle },
  medium: { color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", border: "border-[#F59E0B]/20", icon: AlertTriangle },
  low: { color: "text-[#34D399]", bg: "bg-[#34D399]/10", border: "border-[#34D399]/20", icon: CheckCircle2 },
};

export function AnalysisPanel({ result, isLoading, highlightedClauseId, onClauseClick }: AnalysisPanelProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse rounded-xl bg-muted/50 p-4">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/3 rounded bg-muted" />
                <div className="h-3 w-2/3 rounded bg-muted" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/50 p-8 text-center">
        <Shield className="mb-3 h-10 w-10 text-muted-foreground/40" />
        <h3 className="text-sm font-medium text-muted-foreground">No Analysis Yet</h3>
        <p className="mt-1 text-xs text-muted-foreground/60">
          Upload a document and start an audit to see AI-generated insights here.
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full pr-3">
      <div className="space-y-4 pb-4">
        {/* Summary Card */}
        <Card className="glass-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Executive Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed">{result.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {result.complianceFlags.map((flag) => (
                <Badge key={flag} variant="secondary" className="text-xs bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                  {flag}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Risk Breakdown */}
        <div className="grid grid-cols-4 gap-2">
          {Object.entries(result.riskBreakdown).map(([level, count]) => {
            const config = riskConfig[level as keyof typeof riskConfig];
            const Icon = config.icon;
            return (
              <motion.div
                key={level}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 }}
                className={`flex flex-col items-center rounded-lg border ${config.border} ${config.bg} p-3`}
              >
                <Icon className={`h-4 w-4 ${config.color}`} />
                <span className={`mt-1 text-lg font-bold ${config.color}`}>{count}</span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{level}</span>
              </motion.div>
            );
          })}
        </div>

        <Separator />

        {/* Clause List */}
        <div className="space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Flagged Clauses ({result.clauses.length})
          </h4>
          {result.clauses.map((clause, i) => {
            const config = riskConfig[clause.riskLevel];
            const Icon = config.icon;
            return (
              <motion.div
                key={clause.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card
                  className={`border-l-4 ${config.border.replace("border-", "border-l-")} bg-card/60 cursor-pointer transition-all hover:bg-accent/30 ${highlightedClauseId === clause.id ? "ring-1 ring-primary/40" : ""}`}
                  onClick={() => onClauseClick?.(clause.id)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 rounded-full p-1.5 ${config.bg}`}>
                        <Icon className={`h-3.5 w-3.5 ${config.color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={`text-[10px] capitalize ${config.color}`}>
                            {clause.riskLevel}
                          </Badge>
                          {clause.section && (
                            <span className="text-[10px] text-muted-foreground">{clause.section}</span>
                          )}
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-foreground/90">{clause.text}</p>
                        {clause.recommendation && (
                          <div className="mt-2 rounded-md bg-muted/50 p-2.5 text-xs text-muted-foreground">
                            <span className="font-semibold text-primary">Recommendation: </span>
                            {clause.recommendation}
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </div>
    </ScrollArea>
  );
}

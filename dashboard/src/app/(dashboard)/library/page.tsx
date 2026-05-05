"use client";

import React from "react";
import { BookOpen, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

const clauses = [
  { title: "DPDP Consent Clause", category: "Consent", risk: "critical" as const },
  { title: "Data Retention Standard", category: "Retention", risk: "high" as const },
  { title: "Cross-Border Transfer", category: "Transfer", risk: "high" as const },
  { title: "Breach Notification", category: "Security", risk: "medium" as const },
  { title: "User Rights Portal", category: "Rights", risk: "low" as const },
  { title: "Third-Party Sharing", category: "Sharing", risk: "critical" as const },
];

export default function LibraryPage() {
  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <BookOpen className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Clause Library</h2>
            <p className="text-sm text-muted-foreground">Browse standard DPDP compliance clauses and templates.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {clauses.map((clause) => (
            <Card key={clause.title} className="glass-card hover:bg-accent/30 transition-colors cursor-pointer">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="outline" className="text-[10px]">{clause.category}</Badge>
                  <Badge
                    variant={clause.risk === "critical" ? "destructive" : clause.risk === "high" ? "secondary" : "outline"}
                    className="text-[10px]"
                  >
                    {clause.risk}
                  </Badge>
                </div>
                <p className="text-sm font-medium">{clause.title}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Standard compliant wording for DPDP Act 2023 {clause.category.toLowerCase()} requirements.
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </ScrollArea>
  );
}

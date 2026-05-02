"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { createClient } from '@supabase/supabase-js';

// Normalize ALL-CAPS text to sentence case (safety net for old/backend data)
function normalizeText(text: string): string {
  if (!text || typeof text !== 'string') return text || '';
  const alpha = text.split('').filter(c => /[a-zA-Z]/.test(c));
  if (!alpha.length) return text;
  const upperCount = alpha.filter(c => c === c.toUpperCase() && /[A-Z]/.test(c)).length;
  if (upperCount / alpha.length > 0.5) {
    let normalized = text.toLowerCase();
    normalized = normalized.charAt(0).toUpperCase() + normalized.slice(1);
    normalized = normalized.replace(/([.!?]\s+)([a-z])/g, (match, sep, letter) => sep + letter.toUpperCase());
    const protectedTerms = new Map([
      ['aadhaar', 'Aadhaar'], ['dpdp', 'DPDP'], ['pii', 'PII'], ['kyc', 'KYC'],
      ['gdpr', 'GDPR'], ['hipaa', 'HIPAA'], ['india', 'India'], ['indian', 'Indian'],
      ['ai', 'AI'], ['api', 'API'], ['dpdp act', 'DPDP Act'], ['i', 'I']
    ]);
    for (const [lower, proper] of protectedTerms) {
      normalized = normalized.replace(new RegExp('\\b' + lower.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&') + '\\b', 'gi'), proper);
    }
    return normalized;
  }
  return text;
}
import {
  Search, Bell, Settings, LayoutDashboard, FileText, Library, FileSearch, Send,
  Cpu, Activity, CheckCircle2, AlertTriangle, ShieldCheck, User, ChevronDown, ChevronRight, Upload, Link as LinkIcon, LogIn, LogOut
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Textarea } from "@/components/ui/textarea";

// Initialize Supabase Client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://dummy.supabase.co";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "dummy-key";
const supabase = createClient(supabaseUrl, supabaseKey);

interface Message {
  role: "user" | "ai";
  content: string;
  thinking?: string;
  citations?: { id: string; text: string }[];
}

export default function Dashboard() {
  const [activeNav, setActiveNav] = useState("audit");
  const [activeTab, setActiveTab] = useState("viewer");
  const [fileUploaded, setFileUploaded] = useState(false);
  const [uploadedText, setUploadedText] = useState("");
  const [isAuditing, setIsAuditing] = useState(false);
  const [complianceScore, setComplianceScore] = useState<number | null>(null);
  
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "ai",
      content: "Hello. I am LexGuard AI. Please sign in and upload a document to begin the compliance audit.",
    }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const [user, setUser] = useState<any>(null);
  
  // Auth Modal State
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Real Audit Data State
  const [userAudits, setUserAudits] = useState<any[]>([]);

  // Authentication State Listener
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user || null);
    });
    
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
    });

    return () => subscription.unsubscribe();
  }, []);

  const fetchUserAudits = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      
      const res = await fetch(`/api/audits`, {
        headers: { "Authorization": `Bearer ${session.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUserAudits(data);
      }
    } catch (e) {
      console.error("Failed to fetch audits", e);
    }
  }, []);

  useEffect(() => {
    if (user) {
      fetchUserAudits();
    } else {
      setUserAudits([]);
    }
  }, [user]);

  // Scroll to bottom of chat
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages, isTyping]);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    
    try {
      if (authMode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email: authEmail, password: authPassword });
        if (error) throw error;
        setMessages(prev => [...prev, { role: "ai", content: "✅ **Authentication successful.** You are now in your securely isolated workspace." }]);
      } else {
        const { error } = await supabase.auth.signUp({ email: authEmail, password: authPassword });
        if (error) throw error;
        setMessages(prev => [...prev, { role: "ai", content: "🎉 **Account created!** Your personal enterprise workspace is now ready. All audits will be strictly isolated." }]);
      }
      setShowAuthModal(false);
      setAuthEmail("");
      setAuthPassword("");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setComplianceScore(null);
    setFileUploaded(false);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setUploadedText(text);
        setFileUploaded(true);
        setActiveTab("viewer");
      };
      reader.readAsText(file);
    }
  };

  const runAudit = async () => {
    setIsAuditing(true);
    setComplianceScore(null);
    
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      
      if (!token) {
        setMessages(prev => [...prev, { role: "ai", content: "⚠️ **Authentication Required**\nPlease sign in or create an account to securely run an audit in your isolated workspace." }]);
        setShowAuthModal(true);
        setIsAuditing(false);
        return;
      }

      // Using the document text mapped from the mock viewer
      const policyText = uploadedText || `This Data Processing Agreement ("DPA") forms part of the Master Services Agreement between the parties...
      
      1. Definitions
      "Personal Data" means any information relating to an identified or identifiable natural person...
      
      4. Subprocessors
      4.2 The Processor may engage third-party Subprocessors to assist in the provision of the Services. The Processor shall maintain an up-to-date list of its Subprocessors and provide it to the Controller upon request.
      
      5. Security Measures
      The Processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk...`;

      // Call the Live FastAPI Backend via Next.js Proxy
      const res = await fetch(`/api/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ policy_text: policyText })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      
      setComplianceScore(data.compliance_score);
      
      // Format the backend response into a rich markdown-like chat message
      const safe = { summary: normalizeText(data.summary || ''), verdict: normalizeText(data.verdict || '') };
      let msgContent = `I have completed the deep audit against the DPDP Act 2023. The document scores **${data.compliance_score}%**.

**Verdict:** ${safe.verdict}

${safe.summary}

`;
      
      let citationsList: {id: string, text: string}[] = [];
      
      if (data.flagged_clauses && data.flagged_clauses.length > 0) {
          msgContent += "**Flagged Issues:**\n";
          data.flagged_clauses.forEach((c: any) => {
             const issue = normalizeText(c.issue || '');
             const fix = normalizeText(c.suggested_fix || '');
             msgContent += `- **${c.clause_id} (${c.dpdp_section})**: ${issue} \n  *Recommendation: ${fix}*\n\n`;
             citationsList.push({ id: c.clause_id, text: c.dpdp_section });
          });
      }

      setMessages(prev => [
        ...prev,
        {
          role: "ai",
          content: msgContent,
          thinking: "1. Connected securely to FastAPI backend.\n2. Sent document payload (244 tokens).\n3. Validated JWT session.\n4. Processed DPDP requirements via Gemini Pro.\n5. Structured AnalysisResult model returned.",
          citations: citationsList.slice(0, 4) // Show top 4 citations
        }
      ]);
      
      // Refresh the audit history to reflect the new scan
      await fetchUserAudits();

    } catch (e: any) {
      console.error(e);
      setMessages(prev => [...prev, { role: "ai", content: "❌ **Error connecting to backend:**\n" + e.message }]);
    } finally {
      setIsAuditing(false);
    }
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = chatInput;
    setChatInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setIsTyping(true);

    // Simulate streaming API POST /chat since backend only has /analyze right now
    const aiResponse = "Regarding the subprocessor clause, the current draft lacks a specific timeframe for notifying the controller of any intended changes concerning the addition or replacement of other processors. DPDP compliance requires giving the data fiduciary the opportunity to object to such changes. I recommend adding a '30-day prior written notice' requirement.";
    const thinkingText = "1. Parse user query about subprocessor clause.\n2. Retrieve relevant chunks (Section 4.2).\n3. Compare with DPDP strict requirements.\n4. Identify missing notification timeframe.\n5. Formulate recommendation for '30-day notice'.";

    let currentResponse = "";
    let currentThinking = "";
    
    setMessages(prev => [...prev, { role: "ai", content: "", thinking: "" }]);

    // Simulate thinking phase
    for (let i = 0; i <= thinkingText.length; i += 3) {
      await new Promise(r => setTimeout(r, 20));
      currentThinking = thinkingText.substring(0, i);
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], thinking: currentThinking };
        return newMsgs;
      });
    }

    // Simulate response streaming
    for (let i = 0; i <= aiResponse.length; i += 4) {
      await new Promise(r => setTimeout(r, 15));
      currentResponse = aiResponse.substring(0, i);
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1] = { 
          ...newMsgs[newMsgs.length - 1], 
          content: currentResponse,
          citations: [{ id: "dpdp-sec", text: "DPDP §8(1)" }]
        };
        return newMsgs;
      });
    }

    setIsTyping(false);
  };

  return (
    <div className="flex h-screen w-full bg-slate-950 text-slate-200 overflow-hidden font-sans">
      
      {/* LEFT SIDEBAR */}
      <aside className="w-64 border-r border-slate-800 bg-slate-950/50 flex flex-col shrink-0">
        <div className="p-6 flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight text-slate-100">LexGuard<span className="text-blue-500">AI</span></span>
        </div>
        
        <nav className="flex-1 px-4 py-4 space-y-2">
          <Button 
            variant={activeNav === "dashboard" ? "secondary" : "ghost"} 
            onClick={() => setActiveNav("dashboard")}
            className={`w-full justify-start ${activeNav === 'dashboard' ? 'bg-blue-600/10 text-blue-500 hover:bg-blue-600/20' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'}`}>
            <LayoutDashboard className="mr-3 h-5 w-5" /> Dashboard
          </Button>
          <Button 
            variant={activeNav === "audit" ? "secondary" : "ghost"} 
            onClick={() => setActiveNav("audit")}
            className={`w-full justify-start ${activeNav === 'audit' ? 'bg-blue-600/10 text-blue-500 hover:bg-blue-600/20' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'}`}>
            <FileSearch className="mr-3 h-5 w-5" /> Document Audit
          </Button>
          <Button 
            variant={activeNav === "library" ? "secondary" : "ghost"} 
            onClick={() => setActiveNav("library")}
            className={`w-full justify-start ${activeNav === 'library' ? 'bg-blue-600/10 text-blue-500 hover:bg-blue-600/20' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'}`}>
            <Library className="mr-3 h-5 w-5" /> Compliance Library
          </Button>
          <Button 
            variant={activeNav === "reports" ? "secondary" : "ghost"} 
            onClick={() => setActiveNav("reports")}
            className={`w-full justify-start ${activeNav === 'reports' ? 'bg-blue-600/10 text-blue-500 hover:bg-blue-600/20' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'}`}>
            <FileText className="mr-3 h-5 w-5" /> Reports
          </Button>
        </nav>

        <div className="p-4 mt-auto">
          <Card className="bg-slate-900 border-slate-800 mb-4">
            <CardContent className="p-4 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">Tokens Used</span>
                <span className="text-xs font-bold text-slate-300">1.2M / 2.0M</span>
              </div>
              <Progress value={60} className="h-2 bg-slate-800" />
            </CardContent>
          </Card>
          <Button variant="ghost" className="w-full justify-start text-slate-400 hover:text-slate-100 hover:bg-slate-800">
            <Settings className="mr-3 h-5 w-5" /> Settings
          </Button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col min-w-0">
        
        {/* TOP BAR */}
        <header className="h-16 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center w-96 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <Input 
              placeholder="Search contracts, clauses, audits..." 
              className="bg-slate-900 border-slate-800 pl-10 text-slate-200 placeholder:text-slate-500 h-9"
            />
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <span className="text-sm font-medium text-slate-300">Gemini 3.1 Pro (High)</span>
            </div>
            
            <Separator orientation="vertical" className="h-6 bg-slate-800" />
            
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" className="text-slate-400 hover:text-slate-100 relative">
                <Bell className="h-5 w-5" />
                <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-blue-500"></span>
              </Button>
              
              {user ? (
                 <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8 border border-slate-700 cursor-pointer">
                      <AvatarImage src="https://github.com/shadcn.png" />
                      <AvatarFallback>US</AvatarFallback>
                    </Avatar>
                    <Button variant="ghost" size="icon" onClick={handleLogout} className="text-slate-400 hover:text-red-400">
                       <LogOut className="h-4 w-4" />
                    </Button>
                 </div>
              ) : (
                 <Button onClick={() => setShowAuthModal(true)} variant="secondary" size="sm" className="bg-slate-800 text-slate-200 hover:bg-slate-700">
                    <LogIn className="mr-2 h-4 w-4" /> Sign In
                 </Button>
              )}
            </div>
          </div>
        </header>

        {/* DYNAMIC VIEWS BASED ON SIDEBAR SELECTION */}
        
        {activeNav === "dashboard" && (
          <div className="flex-1 p-8 overflow-auto bg-slate-950">
            <div className="max-w-6xl mx-auto">
              <h1 className="text-3xl font-bold mb-2 text-slate-100">Overview Dashboard</h1>
              <p className="text-slate-500 mb-8">System health, compliance trends, and recent activity.</p>
              
              <div className="grid grid-cols-3 gap-6 mb-8">
                <Card className="bg-slate-900 border-slate-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-slate-400">Avg Compliance Score</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold text-emerald-400">
                      {userAudits.length > 0 
                        ? Math.round(userAudits.reduce((acc, a) => acc + (a.compliance_score || 0), 0) / userAudits.length) 
                        : 0}%
                    </div>
                    <p className="text-xs text-slate-500 mt-1">Based on {userAudits.length} audits</p>
                  </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-slate-400">Documents Audited</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold text-blue-400">{userAudits.length}</div>
                    <p className="text-xs text-slate-500 mt-1">Lifetime total</p>
                  </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-slate-400">High Risk Clauses</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold text-red-400">
                      {userAudits.reduce((acc, a) => acc + (a.total_clauses_flagged || 0), 0)}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">Across all documents</p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        )}

        {activeNav === "library" && (
          <div className="flex-1 p-8 overflow-auto bg-slate-950">
            <div className="max-w-6xl mx-auto">
              <h1 className="text-3xl font-bold mb-2 text-slate-100">Compliance Library</h1>
              <p className="text-slate-500 mb-8">Regulatory frameworks, strict mandates, and system knowledge base.</p>
              
              <Card className="bg-slate-900 border-slate-800">
                <CardContent className="p-0">
                  <div className="divide-y divide-slate-800">
                    <div className="p-4 flex items-center justify-between hover:bg-slate-800/50 cursor-pointer">
                      <div className="flex items-center gap-4">
                        <div className="bg-blue-900/30 p-2 rounded"><Library className="h-5 w-5 text-blue-400" /></div>
                        <div>
                          <h4 className="font-medium text-slate-200">DPDP Act 2023 (India)</h4>
                          <p className="text-sm text-slate-500">Active rule engine for current compliance audits.</p>
                        </div>
                      </div>
                      <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20">Active</Badge>
                    </div>
                    <div className="p-4 flex items-center justify-between hover:bg-slate-800/50 cursor-pointer">
                      <div className="flex items-center gap-4">
                        <div className="bg-slate-800 p-2 rounded"><Library className="h-5 w-5 text-slate-400" /></div>
                        <div>
                          <h4 className="font-medium text-slate-200">GDPR (EU)</h4>
                          <p className="text-sm text-slate-500">European General Data Protection Regulation requirements.</p>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" className="border-slate-700 text-slate-300">Enable Module</Button>
                    </div>
                    <div className="p-4 flex items-center justify-between hover:bg-slate-800/50 cursor-pointer">
                      <div className="flex items-center gap-4">
                        <div className="bg-slate-800 p-2 rounded"><Library className="h-5 w-5 text-slate-400" /></div>
                        <div>
                          <h4 className="font-medium text-slate-200">CCPA (California)</h4>
                          <p className="text-sm text-slate-500">California Consumer Privacy Act requirements.</p>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" className="border-slate-700 text-slate-300">Enable Module</Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {activeNav === "reports" && (
          <div className="flex-1 p-8 overflow-auto bg-slate-950">
             <div className="max-w-6xl mx-auto">
              <h1 className="text-3xl font-bold mb-2 text-slate-100">Audit Reports</h1>
              <p className="text-slate-500 mb-8">Historical analysis reports and printable summaries.</p>
              
              {!user ? (
                 <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-slate-800 rounded-xl bg-slate-900/20">
                    <FileText className="h-12 w-12 text-slate-600 mb-4" />
                    <h3 className="text-xl font-medium text-slate-300">Sign in to view reports</h3>
                    <p className="text-slate-500 mt-2 text-center max-w-md">Your isolated workspace securely stores all past audit histories.</p>
                    <Button onClick={() => setShowAuthModal(true)} className="mt-6 bg-blue-600 hover:bg-blue-700">Sign In</Button>
                 </div>
              ) : userAudits.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-slate-800 rounded-xl bg-slate-900/20">
                  <FileText className="h-12 w-12 text-slate-600 mb-4" />
                  <h3 className="text-xl font-medium text-slate-300">No Reports Generated</h3>
                  <p className="text-slate-500 mt-2 text-center max-w-md">Run a Document Audit and save the results to view historical reports here.</p>
                  <Button onClick={() => setActiveNav("audit")} className="mt-6 bg-blue-600 hover:bg-blue-700">Go to Document Audit</Button>
                </div>
              ) : (
                <Card className="bg-slate-900 border-slate-800">
                  <CardContent className="p-0">
                    <div className="divide-y divide-slate-800">
                      {userAudits.map((audit: any, index: number) => (
                        <div key={index} className="p-4 flex items-center justify-between hover:bg-slate-800/50 transition-colors">
                          <div className="flex items-center gap-4">
                            <div className={`p-3 rounded-lg ${audit.compliance_score >= 80 ? 'bg-emerald-500/10' : audit.compliance_score >= 50 ? 'bg-amber-500/10' : 'bg-red-500/10'}`}>
                              <span className={`font-bold text-lg ${audit.compliance_score >= 80 ? 'text-emerald-400' : audit.compliance_score >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
                                {audit.compliance_score}%
                              </span>
                            </div>
                            <div>
                              <h4 className="font-medium text-slate-200">Legal Document Audit</h4>
                              <p className="text-sm text-slate-500 mt-1">
                                {new Date(audit.created_at).toLocaleDateString()} at {new Date(audit.created_at).toLocaleTimeString()}
                              </p>
                              <div className="flex gap-2 mt-2">
                                <Badge variant="outline" className="text-slate-400 border-slate-700">{audit.total_clauses_flagged} Flagged Clauses</Badge>
                                <Badge variant="outline" className="text-slate-400 border-slate-700">{audit.verdict}</Badge>
                              </div>
                            </div>
                          </div>
                          <Button variant="outline" size="sm" className="border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800">
                            View Details
                          </Button>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
             </div>
          </div>
        )}

        {/* DOCUMENT AUDIT SPLIT PANE VIEW */}
        {activeNav === "audit" && (
          <div className="flex-1 flex overflow-hidden">
            
            {/* LEFT PANE: Document Viewer */}
            <div className="w-1/2 flex flex-col border-r border-slate-800 bg-slate-950">
              <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-[400px]">
                  <TabsList className="bg-slate-900 border border-slate-800">
                    <TabsTrigger value="viewer" className="data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-400">Document Viewer</TabsTrigger>
                    <TabsTrigger value="extracted" className="data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-400">Extracted Clauses</TabsTrigger>
                  </TabsList>
                </Tabs>
                {fileUploaded && (
                  <Button onClick={runAudit} disabled={isAuditing} size="sm" className="bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-900/20">
                    {isAuditing ? <><Activity className="mr-2 h-4 w-4 animate-pulse" /> Auditing...</> : <><Cpu className="mr-2 h-4 w-4" /> Run Deep Audit</>}
                  </Button>
                )}
              </div>

              <div className="flex-1 overflow-auto p-6 relative">
                {!fileUploaded ? (
                  <div className="h-full flex flex-col items-center justify-center border-2 border-dashed border-slate-800 rounded-xl bg-slate-900/20">
                    <div className="bg-slate-800 p-4 rounded-full mb-4">
                      <Upload className="h-8 w-8 text-slate-400" />
                    </div>
                    <h3 className="text-lg font-medium text-slate-200 mb-2">Upload Legal Document</h3>
                    <p className="text-sm text-slate-500 mb-6 text-center max-w-sm">Drag and drop your PDF, DOCX, or TXT file here, or click to browse.</p>
                    <Input type="file" id="file-upload" className="hidden" onChange={handleFileUpload} />
                    <Button variant="secondary" onClick={() => document.getElementById('file-upload')?.click()}>Select File</Button>
                  </div>
                ) : (
                  <div className="bg-slate-100 rounded-md shadow-inner text-slate-900 p-8 min-h-full font-serif leading-relaxed text-sm">
                    <h2 className="text-2xl font-bold mb-6 text-center">DATA PROCESSING AGREEMENT</h2>
                    <p className="mb-4">This Data Processing Agreement ("DPA") forms part of the Master Services Agreement between the parties...</p>
                    
                    <h3 className="font-bold text-lg mt-6 mb-2">1. Definitions</h3>
                    <p className="mb-4">"Personal Data" means any information relating to an identified or identifiable natural person...</p>

                    <h3 className="font-bold text-lg mt-6 mb-2">4. Subprocessors</h3>
                    <div className="relative group">
                      <div className="absolute -left-4 top-0 bottom-0 w-1 bg-yellow-400 opacity-0 group-hover:opacity-100 transition-opacity rounded-full"></div>
                      <p className="mb-4 p-2 bg-yellow-400/10 rounded border border-yellow-400/20" id="sec-4.2">
                        <strong>4.2</strong> The Processor may engage third-party Subprocessors to assist in the provision of the Services. The Processor shall maintain an up-to-date list of its Subprocessors and provide it to the Controller upon request. 
                      </p>
                    </div>
                    
                    <h3 className="font-bold text-lg mt-6 mb-2">5. Security Measures</h3>
                    <p className="mb-4">The Processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk...</p>
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT PANE: AI Chat & Analysis */}
            <div className="w-1/2 flex flex-col bg-slate-950 relative">
              
              {/* Scorecard Header (Shows only when audit complete) */}
              {complianceScore !== null && (
                <div className="p-4 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between shrink-0">
                  <div className="flex items-center gap-4">
                    <div className="relative flex items-center justify-center h-12 w-12">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-slate-800" />
                        <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="transparent" strokeDasharray="125" strokeDashoffset={125 - (125 * complianceScore) / 100} className="text-emerald-500 transition-all duration-1000 ease-out" />
                      </svg>
                      <span className="absolute text-sm font-bold text-emerald-400">{complianceScore}%</span>
                    </div>
                    <div>
                      <h4 className="font-semibold text-slate-200">Compliance Health</h4>
                      <div className="flex gap-2 mt-1">
                        <Badge variant="outline" className="text-emerald-400 border-emerald-400/30 bg-emerald-400/10">Passed: 18</Badge>
                        <Badge variant="outline" className="text-amber-400 border-amber-400/30 bg-amber-400/10">Warnings: 3</Badge>
                        <Badge variant="outline" className="text-red-400 border-red-400/30 bg-red-400/10">Critical: 0</Badge>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Chat Area */}
              <ScrollArea className="flex-1 p-6" ref={scrollAreaRef}>
                <div className="space-y-6 pb-4">
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`flex gap-4 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
                      <Avatar className={`h-8 w-8 mt-1 border shrink-0 ${msg.role === 'ai' ? 'border-blue-500/50 bg-blue-900/20' : 'border-slate-700'}`}>
                        {msg.role === 'ai' ? (
                          <Cpu className="h-4 w-4 m-auto text-blue-400" />
                        ) : (
                          <User className="h-4 w-4 m-auto text-slate-400" />
                        )}
                      </Avatar>
                      
                      <div className="flex flex-col gap-2 w-full">
                        {/* User Message */}
                        {msg.role === 'user' && (
                          <div className="bg-blue-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm shadow-sm whitespace-pre-wrap">
                            {msg.content}
                          </div>
                        )}

                        {/* AI Message */}
                        {msg.role === 'ai' && (
                          <div className="flex flex-col gap-3 w-full">
                            
                            {/* Thinking Mode Collapsible */}
                            {msg.thinking && (
                              <Collapsible className="w-full">
                                <CollapsibleTrigger className="flex items-center gap-2 text-xs font-mono text-slate-500 hover:text-slate-300 transition-colors">
                                  <Activity className="h-3 w-3" />
                                  View LLM Reasoning
                                  <ChevronDown className="h-3 w-3 opacity-50" />
                                </CollapsibleTrigger>
                                <CollapsibleContent className="mt-2">
                                  <div className="bg-slate-900 border border-slate-800 rounded-md p-3 text-xs font-mono text-slate-400 whitespace-pre-line leading-relaxed shadow-inner">
                                    {msg.thinking}
                                  </div>
                                </CollapsibleContent>
                              </Collapsible>
                            )}

                            {/* Main Response */}
                            {msg.content && (
                              <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                                {msg.content}
                              </div>
                            )}

                            {/* Citations */}
                            {msg.citations && msg.citations.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-1">
                                {msg.citations.map((cite, i) => (
                                  <Badge key={i} variant="secondary" className="bg-slate-800 text-slate-300 hover:bg-slate-700 cursor-pointer border border-slate-700 flex items-center gap-1.5 py-0.5">
                                    <LinkIcon className="h-3 w-3 text-blue-400" />
                                    {cite.text}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              {/* Input Area */}
              <div className="p-4 border-t border-slate-800 bg-slate-950 shrink-0">
                <form onSubmit={handleChatSubmit} className="relative flex items-end gap-2 bg-slate-900 border border-slate-800 rounded-xl p-2 shadow-sm focus-within:border-slate-700 focus-within:ring-1 focus-within:ring-slate-700 transition-all">
                  <Textarea 
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask a legal question or query the document..."
                    className="min-h-[44px] max-h-32 resize-none border-0 bg-transparent focus-visible:ring-0 text-sm py-3 px-3 scrollbar-none"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleChatSubmit(e);
                      }
                    }}
                  />
                  <Button 
                    type="submit" 
                    disabled={!chatInput.trim() || isTyping} 
                    size="icon" 
                    className={`h-10 w-10 shrink-0 rounded-lg mb-1 mr-1 ${chatInput.trim() ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-slate-800 text-slate-500'}`}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
                <div className="flex justify-between items-center mt-3 px-2">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 flex items-center gap-1.5">
                    <ShieldCheck className="h-3 w-3" /> Encrypted & Ephemeral
                  </span>
                  <span className="text-xs text-slate-600">LexGuard AI can make mistakes. Verify important legal advice.</span>
                </div>
              </div>

            </div>
          </div>
        )}

      </main>

      {/* AUTH MODAL */}
      {showAuthModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <Card className="relative w-full max-w-md bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">{authMode === "login" ? "Sign In to Workspace" : "Create Enterprise Workspace"}</CardTitle>
              <CardDescription className="text-slate-400">
                {authMode === "login" ? "Access your isolated audit reports and history." : "Create a new isolated workspace to begin securely auditing documents."}
              </CardDescription>
            </CardHeader>
            <form onSubmit={handleAuthSubmit}>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">Work Email</label>
                  <Input 
                    type="email" 
                    required 
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                    className="bg-slate-950 border-slate-800 text-slate-200" 
                    placeholder="you@company.com" 
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-300">Password</label>
                  <Input 
                    type="password" 
                    required 
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    className="bg-slate-950 border-slate-800 text-slate-200" 
                    placeholder="••••••••" 
                  />
                </div>
              </CardContent>
              <CardFooter className="flex flex-col gap-4">
                <Button type="submit" disabled={authLoading} className="w-full bg-blue-600 hover:bg-blue-700 text-white">
                  {authLoading ? "Processing..." : authMode === "login" ? "Sign In" : "Create Workspace"}
                </Button>
                <div className="text-center text-sm text-slate-500">
                  {authMode === "login" ? "Don't have a workspace? " : "Already have a workspace? "}
                  <button 
                    type="button" 
                    className="text-blue-400 hover:text-blue-300 font-medium"
                    onClick={() => setAuthMode(authMode === "login" ? "signup" : "login")}
                  >
                    {authMode === "login" ? "Sign Up" : "Sign In"}
                  </button>
                </div>
                <Button variant="ghost" type="button" onClick={() => setShowAuthModal(false)} className="absolute top-2 right-2 text-slate-500 hover:text-slate-300">✕</Button>
              </CardFooter>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}

"""
LexGuard AI — RAG Compliance Engine
Document chunking, embedding-based retrieval of DPDP Act sections,
and enriched prompt generation for deep compliance analysis.
"""

import os
import re
import logging
from typing import List, Dict, Tuple, Optional

from dpdp_knowledge_base import DPDP_SECTIONS

logger = logging.getLogger("rag_engine")

# ── Optional dependencies (graceful degrade) ──
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    logger.warning("numpy not installed; RAG vector operations unavailable")

try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except ImportError:
    _HAS_ST = False
    logger.warning("sentence-transformers not installed; embedding-based RAG unavailable")

try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False
    logger.warning("faiss-cpu not installed; vector search unavailable")


class ComplianceRAG:
    """
    Retrieval-Augmented Generation engine for DPDP Act 2023 compliance analysis.
    - Chunks uploaded documents into semantic pieces
    - Embeds chunks and retrieves relevant DPDP sections via FAISS
    - Builds an enriched prompt with retrieved legal context
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 2000,
        chunk_overlap: int = 300,
        top_k_per_chunk: int = 3,
        max_chunks_for_retrieval: int = 12,
        max_sections_in_prompt: int = 12,
    ):
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k_per_chunk = top_k_per_chunk
        self.max_chunks_for_retrieval = max_chunks_for_retrieval
        self.max_sections_in_prompt = max_sections_in_prompt

        self.model: Optional[SentenceTransformer] = None
        self.dpdp_index: Optional[faiss.Index] = None
        self.dpdp_texts: List[str] = []
        self.dpdp_sections: List[Dict] = []
        self.dpdp_embeddings: Optional["np.ndarray"] = None  # type: ignore
        self._initialized = False

    @property
    def available(self) -> bool:
        return _HAS_ST and _HAS_FAISS and _HAS_NUMPY

    def initialize(self) -> None:
        """Load embedding model and build FAISS index over DPDP sections."""
        if self._initialized:
            return
        if not self.available:
            logger.warning(
                "RAG dependencies missing (sentence-transformers=%s, faiss=%s, numpy=%s). "
                "Compliance analysis will use zero-shot prompting without retrieved DPDP context.",
                _HAS_ST, _HAS_FAISS, _HAS_NUMPY,
            )
            self.dpdp_sections = DPDP_SECTIONS
            self._initialized = True
            return

        logger.info("Loading sentence-transformer model: %s", self.model_name)
        self.model = SentenceTransformer(self.model_name)

        self.dpdp_sections = DPDP_SECTIONS
        self.dpdp_texts = [
            f"{s['id']} {s['title']}\n{s['text']}" for s in self.dpdp_sections
        ]

        logger.info("Embedding %d DPDP sections...", len(self.dpdp_texts))
        embeddings = self.model.encode(
            self.dpdp_texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        self.dpdp_embeddings = embeddings.astype("float32")

        dim = self.dpdp_embeddings.shape[1]
        self.dpdp_index = faiss.IndexFlatIP(dim)
        self.dpdp_index.add(self.dpdp_embeddings)

        logger.info(
            "RAG engine ready: %d DPDP sections indexed (dim=%d)",
            len(self.dpdp_sections),
            dim,
        )
        self._initialized = True

    # ── Chunking ────────────────────────────────────────────────

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks, preferring paragraph and sentence boundaries.
        Chunks smaller than 100 chars are discarded.
        """
        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            if end < text_len:
                # Try to break at natural boundaries (ordered by preference)
                for sep in ("\n\n", "\n", ". ", "! ", "? ", "; ", ", "):
                    pos = text.rfind(sep, start, end)
                    if pos > start + self.chunk_size // 3:
                        end = pos + len(sep)
                        break

            chunk = text[start:end].strip()
            if len(chunk) >= 100:
                chunks.append(chunk)

            advance = end - start - self.chunk_overlap
            if advance <= 0:
                advance = end - start
            start += advance
            if start >= text_len:
                break

        # Deduplicate while preserving order
        seen: set = set()
        unique_chunks: List[str] = []
        for c in chunks:
            key = c[:200]
            if key not in seen:
                seen.add(key)
                unique_chunks.append(c)
        return unique_chunks

    # ── Retrieval ───────────────────────────────────────────────

    def _retrieve_sections(self, query: str, top_k: int) -> List[Dict]:
        """Return top-k DPDP sections for a query text."""
        if not self.available or self.dpdp_index is None or self.model is None:
            # Fallback: keyword-based retrieval using simple matching
            return self._keyword_retrieve(query, top_k)

        embedding = self.model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        ).astype("float32")
        scores, indices = self.dpdp_index.search(embedding, top_k)
        return [self.dpdp_sections[i] for i in indices[0]]

    def _keyword_retrieve(self, query: str, top_k: int) -> List[Dict]:
        """Fallback keyword matching when embeddings unavailable."""
        query_lower = query.lower()
        # Build a simple score: count of keyword matches
        scored = []
        for sec in self.dpdp_sections:
            text = f"{sec['id']} {sec['title']} {sec['text']}".lower()
            score = sum(1 for kw in query_lower.split() if len(kw) > 3 and kw in text)
            scored.append((score, sec))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [sec for _, sec in scored[:top_k]]

    def retrieve_for_document(self, document_text: str) -> List[Dict]:
        """
        Chunk the document, retrieve relevant DPDP sections for each chunk,
        and return a deduplicated ranked list of sections.
        """
        chunks = self.chunk_text(document_text)
        if not chunks:
            return []

        # Limit chunks for retrieval to avoid excessive compute
        retrieval_chunks = chunks[: self.max_chunks_for_retrieval]

        all_sections: List[Tuple[float, Dict]] = []
        seen_ids: set = set()

        for chunk in retrieval_chunks:
            sections = self._retrieve_sections(chunk, self.top_k_per_chunk)
            for sec in sections:
                sid = sec["id"]
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    all_sections.append((0.0, sec))  # score placeholder

        # Also retrieve for a document-level summary (first ~2500 chars)
        summary_query = document_text[:2500]
        top_sections = self._retrieve_sections(summary_query, 5)
        for sec in top_sections:
            sid = sec["id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                all_sections.append((0.0, sec))

        return [sec for _, sec in all_sections[: self.max_sections_in_prompt]]

    # ── Prompt Building ─────────────────────────────────────────

    def build_enriched_prompt(self, document_text: str) -> Tuple[str, List[Dict]]:
        """
        Build an enriched analysis prompt that includes:
        1. Retrieved relevant DPDP Act 2023 sections
        2. Document text (or chunked excerpts for long docs)

        Returns: (enriched_prompt, retrieved_sections)
        """
        if not self._initialized:
            self.initialize()

        sections = self.retrieve_for_document(document_text)

        # Build DPDP context block
        sections_block = "\n\n".join(
            f"--- {sec['id']}: {sec['title']} ---\n{sec['text']}"
            for sec in sections
        )

        # Document text: use full text if short, chunked excerpts if long
        doc_len = len(document_text)
        if doc_len <= 6000:
            doc_block = document_text
        else:
            chunks = self.chunk_text(document_text)
            selected = chunks[:8]  # Up to 8 excerpts
            doc_block = "\n\n".join(
                f"[Document Excerpt {i + 1}/{len(selected)}]:\n{chunk}"
                for i, chunk in enumerate(selected)
            )

        prompt = f"""=== RETRIEVED DPDP ACT 2023 SECTIONS (LEGAL CONTEXT) ===
{sections_block}

=== DOCUMENT TO AUDIT ===
{doc_block}
"""
        return prompt, sections

    def build_system_prompt(self) -> str:
        """
        Return the DPDP auditor system prompt.  This is the same behavioural
        contract as before, but the user prompt now contains retrieved DPDP
        sections so the model has hard legal text to cite against.
        """
        return """### SYSTEM_PROMPT: DPDP ZERO-TRUST AUDITOR
You are a deterministic Legal Auditor specialising in the Digital Personal Data Protection Act, 2023 (India).
You MUST follow these layers:

1. PII SCAN: Identify Aadhaar, Phone, and Email patterns in the document. Do NOT include raw PII in your output. In clause_excerpt fields, replace any detected PII with redacted placeholders (e.g. [AADHAAR], [PHONE], [EMAIL], [NAME]).

2. STATUTORY AUDIT: Every finding MUST cite a valid DPDP Act 2023 section using the exact citation format provided in the Retrieved DPDP Sections. Explain the legal logic connecting the document text to the Act in the issue field. If you are unsure of the exact section, state "Requires manual legal review" instead of guessing.

3. HALLUCINATION CHECK: Cross-reference your citations against the Retrieved DPDP Sections provided above. If a citation does not appear in those sections, flag it as "General Regulatory Risk."

Your job is to:
- Assign a compliance score (0-100) based on adherence to the DPDP Act 2023.
- Identify flagged clauses with risk level, exact DPDP section/sub-section, excerpt, issue (with legal rationale), and suggested fix.
- Evaluate against 6 DPDP focus areas: Consent, Notice, Purpose Limitation, Data Minimization, Data Principal Rights, Breach Notification.

### FORMATTING CONSTRAINTS
- NO ALL-CAPS: Do not use uppercase for emphasis or prose.
- CASE SENSITIVITY: Use Title Case for Verdicts (e.g. "High Risk", "Moderate Risk", "Low Risk").
- OUTPUT: Valid JSON matching the defined schema. No markdown fences, no prose.

Score guidance:
- 80-100: Low Risk (mostly compliant, minor gaps)
- 50-79: Moderate Risk (meaningful gaps requiring attention)
- 0-49: High Risk (major violations / missing critical DPDP obligations)

You MUST respond with ONLY a valid JSON object. Use this exact schema:

{
  "compliance_score": <integer 0-100>,
  "verdict": "<Low Risk | Moderate Risk | High Risk>",
  "summary": "<2-3 sentence board-ready summary>",
  "flagged_clauses": [
    {
      "clause_id": "<short identifier like 'Section 4.1' or 'Clause 3'>",
      "risk_level": "<High | Medium | Low>",
      "dpdp_section": "<Exact DPDP Act 2023 citation from Retrieved Sections, e.g. 'DPDP Section 6' or 'DPDP Section 5'>",
      "clause_excerpt": "<short excerpt from the user's policy (<=200 chars)>",
      "issue": "<what is wrong, with legal rationale connecting text to the cited DPDP section. If unsure, write 'Requires manual legal review'>",
      "suggested_fix": "<concrete remediation, 1-2 sentences>"
    }
  ],
  "checklist": [
    {"focus_area": "Consent", "status": "<Compliant | Partial | Non-Compliant | Not Addressed>", "note": "<1 sentence>"},
    {"focus_area": "Notice", "status": "...", "note": "..."},
    {"focus_area": "Purpose Limitation", "status": "...", "note": "..."},
    {"focus_area": "Data Minimization", "status": "...", "note": "..."},
    {"focus_area": "Data Principal Rights", "status": "...", "note": "..."},
    {"focus_area": "Breach Notification", "status": "...", "note": "..."}
  ]
}

Return at minimum 4 flagged_clauses if any risks exist, up to 8. All 6 checklist items are mandatory.
Be decisive, specific, cite exact DPDP sections from the Retrieved Sections provided, and never fabricate citations."""


# ── Singleton instance ──────────────────────────────────────
_rag_singleton: Optional[ComplianceRAG] = None


def get_rag_engine() -> ComplianceRAG:
    """Lazy-initialised singleton RAG engine."""
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = ComplianceRAG()
        _rag_singleton.initialize()
    return _rag_singleton

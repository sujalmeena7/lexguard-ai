"""
LexGuard RAG Optimization Module
================================
Implements the Lead AI Engineer's strategy for Hybrid Search (BM25 + Semantic)
using Supabase and Reciprocal Rank Fusion (RRF).

Includes:
1. Automated Metadata Tagging logic
2. Hybrid Search retrieval pattern
3. SARAL-compliant prompt caching strategy
"""

import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timezone

# ── Metadata Tagging Schema ──────────────────────────────────────────
# Use this to automatically tag documents during the ingestion phase.
# This allows for instant filtering in the React frontend.

def extract_metadata_tags(analysis_result: Dict) -> Dict:
    """
    Transforms audit findings into database metadata tags.
    Example: Detects "Cross-border transfer" and sets a high_risk flag.
    """
    tags = {
        "category": analysis_result.get("document_category", "Privacy Policy"),
        "jurisdiction": "DPDP 2023",
        "has_pii": False,
        "high_risk_transfer": False,
        "retention_policy_detected": False,
        "saral_compliance_score": 0
    }
    
    # Logic to set flags based on audit findings
    audit_text = str(analysis_result).lower()
    if "cross-border" in audit_text or "outside india" in audit_text:
        tags["high_risk_transfer"] = True
    if "aadhaar" in audit_text or "phone number" in audit_text:
        tags["has_pii"] = True
    if "30 days" in audit_text or "retention" in audit_text:
        tags["retention_policy_detected"] = True
        
    return tags

# ── Hybrid Search Implementation (Supabase Pattern) ──────────────────
# This pattern combines BM25 keyword matching with Semantic vector search.

def hybrid_search_query(
    query: str, 
    vector_query: str, 
    bm25_anchors: List[str],
    limit: int = 5
) -> str:
    """
    Generates the SQL or RPC call for Supabase Hybrid Search.
    Uses Reciprocal Rank Fusion (RRF) to combine results.
    """
    
    # This is a conceptual implementation of the Supabase match_documents logic
    # with an added keyword (BM25) component.
    
    sql_logic = f"""
    -- 1. Keyword Match (BM25)
    WITH keyword_search AS (
      SELECT id, rank() OVER (ORDER BY ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', '{' '.join(bm25_anchors)}')) DESC) as rank
      FROM documents
      WHERE to_tsvector('english', content) @@ plainto_tsquery('english', '{' '.join(bm25_anchors)}')
      LIMIT 20
    ),
    -- 2. Semantic Match (Vector)
    vector_search AS (
      SELECT id, rank() OVER (ORDER BY embedding <=> '{vector_query}'::vector) as rank
      FROM documents
      ORDER BY embedding <=> '{vector_query}'::vector
      LIMIT 20
    )
    -- 3. Combine with Reciprocal Rank Fusion (RRF)
    SELECT 
      COALESCE(k.id, v.id) as id,
      (1.0 / (60 + COALESCE(k.rank, 100))) + (1.0 / (60 + COALESCE(v.rank, 100))) as score
    FROM keyword_search k
    FULL OUTER JOIN vector_search v ON k.id = v.id
    ORDER BY score DESC
    LIMIT {limit};
    """
    return sql_logic

# ── Prompt Caching Strategy ──────────────────────────────────────────
# Separates static instructions from dynamic audit data to minimize
# latency and token costs on supported providers (e.g. Gemini, Anthropic).

def get_cached_audit_prompt(user_text: str, context: str) -> List[Dict]:
    """
    Constructs a prompt structured for efficient caching.
    The 'System Role' and 'Legal Constraints' remain static.
    """
    return [
        {
            "role": "system",
            "content": "You are a Senior Legal Compliance Officer auditing for DPDP Act 2023. [STATIC_ROLE_DEFINITION]"
        },
        {
            "role": "user",
            "content": f"AUDIT_TARGET: {user_text}\n\nLEGAL_CONTEXT: {context}"
        }
    ]

if __name__ == "__main__":
    # Example usage for testing metadata logic
    mock_audit = {"audit_result": "This clause allows cross-border transfer of Aadhaar data."}
    print(json.dumps(extract_metadata_tags(mock_audit), indent=2))

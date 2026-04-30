"""
DPDP Act 2023 – Legal Compliance Auditor (RAG System)
=====================================================
Uses a 2-tier ParentDocumentRetriever for context-aware extraction,
persists parent documents to disk, and introduces an automated
"Audit Engine" mode.
"""

import os
import re
import sys
import glob
import json
import textwrap
import streamlit as st
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── LangChain core
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.stores import InMemoryStore
from langchain_core.documents import Document
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ── Paths 
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
DB_DIR     = os.path.join(BASE_DIR, "db")
STORE_PATH = os.path.join(BASE_DIR, "docstore.json")
WORKSPACE_DB_DIR = os.path.join(BASE_DIR, "db_workspace")
WORKSPACE_COLLECTION = "user_workspace_chunks"

# ── Configuration ───────────────────────────────────────────────────
EMBED_MODEL   = "all-MiniLM-L6-v2"

# Two-layer audit architecture:
#   Layer 1 (TRIAGE_MODEL): fast, cheap classifier that screens every chunk in parallel.
#   Layer 2 (DEEP_MODEL):   slower, more accurate model invoked ONLY on chunks the
#                           triage layer marked as needing review.
# This typically cuts audit time by 5-10x and Pro-tier API spend by 70-90%, while
# preserving the rigor of Pro on the clauses that actually matter.
TRIAGE_MODEL  = "gemini-2.0-flash"
DEEP_MODEL    = "gemini-1.5-pro"
# Kept for backward compatibility (used by build_chain / interactive Q&A).
GEMINI_MODEL  = DEEP_MODEL

TRIAGE_CONCURRENCY = 8   # Flash tolerates high RPM
DEEP_CONCURRENCY   = 3   # Pro RPM is much lower; stay conservative

COLLECTION    = "dpdp_parent_child"

# ── Prompts ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""\
    You are a Legal Compliance Auditor. Use the provided context from the
    DPDP Act 2023 to answer the user's question.  If the answer is not in
    the context, state that the document does not address this.  Be precise
    and cite the Section number if available.

    Context:
    {context}

    Question: {question}

    Answer:""")

PROMPT = PromptTemplate(
    template=SYSTEM_PROMPT,
    input_variables=["context", "question"],
)

AUDIT_PROMPT_STR = textwrap.dedent("""\
    You are a Senior Legal Compliance Officer. Compare the following Company Clause to the DPDP Act 2023.
    
    Company Clause: {user_text}
    
    Legal Context: {context}
    
    Instructions: Identify if the clause is Compliant, Non-Compliant, or Partially Compliant. If Non-Compliant, specify the exact Section of the DPDP Act and provide a 'Suggested Correction'. Do not add any conversational filler.
    """)

AUDIT_PROMPT = PromptTemplate(
    template=AUDIT_PROMPT_STR,
    input_variables=["context", "user_text"],
)

# Layer-1 triage prompt: must return ONLY a tight JSON object so we can parse
# deterministically and route flagged clauses into the deep-audit layer.
TRIAGE_PROMPT_STR = textwrap.dedent("""\
    You are a fast DPDP Act 2023 compliance triage agent. Classify the Company Clause
    against the Legal Context. Return ONLY a single valid JSON object. No markdown,
    no code fences, no commentary.

    Schema:
    {{
      "verdict": "COMPLIANT" | "REVIEW_NEEDED" | "NON_COMPLIANT",
      "risk_level": "Low" | "Medium" | "High",
      "reason": "<one short sentence, max 25 words>"
    }}

    Decision rules:
    - COMPLIANT (Low): clause clearly aligns with DPDP requirements, no material gaps.
    - REVIEW_NEEDED (Medium): clause is ambiguous, partial, or has minor concerns worth deeper review.
    - NON_COMPLIANT (High): clause omits or violates a DPDP obligation.

    Company Clause:
    {user_text}

    Legal Context:
    {context}

    Return JSON only.
    """)

TRIAGE_PROMPT = PromptTemplate(
    template=TRIAGE_PROMPT_STR,
    input_variables=["context", "user_text"],
)


def _extract_triage_json(text: str) -> dict:
    """Robustly extract the triage JSON object from a model response."""
    if not text:
        raise ValueError("Empty triage response")
    # 1) raw
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 2) strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 3) first { ... last }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise json.JSONDecodeError("Triage JSON not found", text, 0)

# =====================================================================
# Persistent Store Wrapper
# =====================================================================
class PersistentDocStore(InMemoryStore):
    """Wraps InMemoryStore to save/load Document objects via JSON to disk."""
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    for k, v in data.items():
                        self.store[k] = Document(**v)
                except Exception as e:
                    print(f"Warning: Could not load store from {path}: {e}")

    def mset(self, key_value_pairs):
        super().mset(key_value_pairs)
        self._save()

    def mdelete(self, keys):
        super().mdelete(keys)
        self._save()

    def _save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            data = {k: {"page_content": v.page_content, "metadata": v.metadata} 
                    for k, v in self.store.items()}
            json.dump(data, f, indent=2)


# =====================================================================
# 1.  PDF Ingestion & Setup
# =====================================================================
def get_retriever(ingest: bool = False) -> ParentDocumentRetriever:
    """Builds and returns the ParentDocumentRetriever."""
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    
    vectorstore = Chroma(
        persist_directory=DB_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION,
    )
    
    store = PersistentDocStore(STORE_PATH)

    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=store,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
        search_kwargs={"k": 5}
    )

    if ingest:
        pdf_paths = glob.glob(os.path.join(DATA_DIR, "*.pdf"))
        if not pdf_paths:
            print(f"\n⚠  No PDF files found in {DATA_DIR} to ingest.")
            sys.exit(1)

        docs = []
        for path in pdf_paths:
            print(f"  📄  Loading: {os.path.basename(path)}")
            loader = PyPDFLoader(path)
            docs.extend(loader.load())
            
        print(f"  ⏳  Embedding {len(docs)} pages... (this may take a moment)")
        retriever.add_documents(docs, ids=None)
        print("  ✔  Ingestion to ChromaDB and Local DocStore complete!\n")

    return retriever


def _load_user_document(user_doc_path: str):
    """Load a user-provided PDF or TXT into LangChain documents."""
    if user_doc_path.lower().endswith(".txt"):
        from langchain_community.document_loaders import TextLoader

        loader = TextLoader(user_doc_path, encoding="utf-8")
    else:
        loader = PyPDFLoader(user_doc_path)

    return loader.load()


def _safe_namespace_token(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in value)


def get_document_namespace(user_id: str, user_doc_path: str) -> str:
    user_token = _safe_namespace_token(user_id)
    source_token = _safe_namespace_token(os.path.basename(user_doc_path))
    return f"{user_token}:{source_token}"


def index_user_document(user_id: str, user_doc_path: str) -> int:
    """Index user document chunks with user_id metadata for isolated retrieval."""
    user_docs = _load_user_document(user_doc_path)
    if not user_docs:
        return 0
    document_namespace = get_document_namespace(user_id, user_doc_path)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    user_chunks = splitter.split_documents(user_docs)
    for chunk in user_chunks:
        chunk.metadata = {
            **chunk.metadata,
            "user_id": user_id,
            "source_path": os.path.basename(user_doc_path),
            "document_namespace": document_namespace,
        }

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = Chroma(
        persist_directory=WORKSPACE_DB_DIR,
        embedding_function=embeddings,
        collection_name=WORKSPACE_COLLECTION,
    )
    vectorstore.add_documents(user_chunks)
    return len(user_chunks)


def get_user_workspace_retriever(user_id: str, k: int = 4, document_namespace: Optional[str] = None):
    """Create a user-scoped retriever that filters vectors by user_id and optional document namespace."""
    # ChromaDB >=0.5 requires explicit $eq operator in where clauses.
    conditions = [{"user_id": {"$eq": user_id}}]
    if document_namespace:
        conditions.append({"document_namespace": {"$eq": document_namespace}})
    metadata_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = Chroma(
        persist_directory=WORKSPACE_DB_DIR,
        embedding_function=embeddings,
        collection_name=WORKSPACE_COLLECTION,
    )
    return vectorstore.as_retriever(
        search_kwargs={"k": k, "filter": metadata_filter}
    )


def get_user_workspace_vector_stats(user_id: str, document_namespace: Optional[str] = None) -> Dict[str, int]:
    conditions = [{"user_id": {"$eq": user_id}}]
    if document_namespace:
        conditions.append({"document_namespace": {"$eq": document_namespace}})
    metadata_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

    vectorstore = Chroma(
        persist_directory=WORKSPACE_DB_DIR,
        collection_name=WORKSPACE_COLLECTION,
    )
    vector_data = vectorstore.get(where=metadata_filter, include=[])
    return {"total_chunks": len(vector_data.get("ids", []))}


# =====================================================================
# 2.  Retrieval-QA Chain (Interactive)
# =====================================================================
def build_chain(retriever: ParentDocumentRetriever):
    google_key = st.secrets.get('GOOGLE_API_KEY')
    if not google_key:
        raise ValueError("GOOGLE_API_KEY not found in Streamlit secrets.")

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=google_key, temperature=0)
    
    # Modern approach: create_stuff_documents_chain expects "context" and "question"
    # We use a ChatPromptTemplate to wrap our SYSTEM_PROMPT
    prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
    
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(retriever, combine_docs_chain)
    return chain

def interactive_loop(chain) -> None:
    print("\n-- Interactive RAG Mode --")
    while True:
        try:
            question = input("🔎  Your question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nReturning to menu...")
            break

        if not question: continue
        if question.lower() in {"quit", "exit", "q", "back"}: break

        print("\n⏳  Thinking …\n")
        try:
            # create_retrieval_chain uses "input" instead of "query" by default
            result = chain.invoke({"input": question})
            print("=" * 64)
            print("📝  ANSWER")
            print("=" * 64)
            print(result["answer"])
        except Exception as e:
            print(f"❌ Error invoking model: {e}")


# =====================================================================
# 3.  Compliance Audit Engine
# =====================================================================
def run_compliance_audit(
    retriever: ParentDocumentRetriever,
    user_doc_path: str = None,
    progress_callback=None,
    user_workspace_retriever=None,
    report_output_path: Optional[str] = None,
):
    print("\n-- Compliance Audit Mode --")
    if user_doc_path is None:
        user_doc_path = input("📂 Enter the path to the PDF or TXT document to audit: ").strip()
    
    if not os.path.isfile(user_doc_path):
        print(f"❌ File not found at: {user_doc_path}")
        return

    try:
        user_docs = _load_user_document(user_doc_path)
    except Exception as e:
        print(f"❌ Failed to read document: {e}")
        return

    if not user_docs:
        print("⚠  No text found in the provided PDF.")
        return

    # Split user doc into chunks roughly 3-4 sentences long
    audit_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    audit_chunks = audit_splitter.split_documents(user_docs)

    google_key = st.secrets.get('GOOGLE_API_KEY')
    if not google_key:
        print("❌ Error: GOOGLE_API_KEY not found in Streamlit secrets.")
        return []

    # Layer 1: fast Flash classifier  |  Layer 2: deep Pro auditor
    triage_llm = ChatGoogleGenerativeAI(
        model=TRIAGE_MODEL, google_api_key=google_key, temperature=0
    )
    deep_llm = ChatGoogleGenerativeAI(
        model=DEEP_MODEL, google_api_key=google_key, temperature=0
    )

    total = len(audit_chunks)
    print(f"\n🔍 Analyzing {total} sections via two-layer audit "
          f"({TRIAGE_MODEL} → {DEEP_MODEL})...\n")

    # ---- Step A: pre-fetch retrieval contexts once (local, fast) -----------
    contexts = [""] * total
    for idx, chunk in enumerate(audit_chunks):
        legal_docs = retriever.invoke(chunk.page_content)
        ctx = "\n\n".join(d.page_content for d in legal_docs)
        if user_workspace_retriever is not None:
            ws_docs = user_workspace_retriever.invoke(chunk.page_content)
            if ws_docs:
                ws_ctx = "\n\n".join(d.page_content for d in ws_docs)
                ctx = f"{ctx}\n\nUser Workspace Context (isolated):\n{ws_ctx}"
        contexts[idx] = ctx

    # ---- Step B: layer-1 triage + layer-2 deep audit, pipelined ------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _triage_call(user_text: str, context: str) -> dict:
        raw = triage_llm.invoke(
            TRIAGE_PROMPT.format(user_text=user_text, context=context)
        )
        text = raw.content if hasattr(raw, "content") else str(raw)
        return _extract_triage_json(text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _deep_call(user_text: str, context: str) -> str:
        raw = deep_llm.invoke(
            AUDIT_PROMPT.format(user_text=user_text, context=context)
        )
        return raw.content if hasattr(raw, "content") else str(raw)

    triage_results: Dict[int, dict] = {}
    deep_results: Dict[int, str] = {}
    finalized: Dict[int, dict] = {}
    completed = 0

    def _build_record(i: int) -> dict:
        chunk = audit_chunks[i]
        triage = triage_results.get(i) or {
            "verdict": "REVIEW_NEEDED", "risk_level": "Medium",
            "reason": "Triage unavailable."
        }
        deep_text = deep_results.get(i)

        if deep_text is not None:
            audit_text = deep_text
        else:
            # COMPLIANT path: build a concise human-readable summary so
            # downstream consumers (report_gen, UI) keep working unchanged.
            audit_text = (
                f"Compliant. {triage.get('reason', '').strip()}".strip()
            )

        verdict = (triage.get("verdict") or "").upper()
        risk = (triage.get("risk_level") or "").capitalize()
        is_high = ("Non-Compliant" in audit_text) or verdict == "NON_COMPLIANT"
        if is_high:
            status = "High Risk"
        elif verdict == "REVIEW_NEEDED" or risk == "Medium":
            status = "Medium Risk"
        else:
            status = "Compliant"

        return {
            "clause_id": i + 1,
            "page_num": chunk.metadata.get("page", 0) + 1,
            "clause_text": chunk.page_content,
            "audit_result": audit_text,
            "status": status,
            "triage_verdict": verdict or "REVIEW_NEEDED",
            "triage_risk_level": risk or "Medium",
            "triage_reason": triage.get("reason", ""),
        }

    triage_pool = ThreadPoolExecutor(
        max_workers=TRIAGE_CONCURRENCY, thread_name_prefix="triage"
    )
    deep_pool = ThreadPoolExecutor(
        max_workers=DEEP_CONCURRENCY, thread_name_prefix="deep"
    )

    try:
        # Submit every chunk to layer-1 triage in parallel.
        triage_futs = {
            triage_pool.submit(
                _triage_call, audit_chunks[i].page_content, contexts[i]
            ): i
            for i in range(total)
        }
        deep_futs: Dict = {}

        # As triage results stream in, immediately finalize compliant chunks
        # and pipeline flagged chunks into the deep auditor.
        for fut in as_completed(triage_futs):
            i = triage_futs[fut]
            try:
                triage = fut.result()
            except Exception as e:
                # On triage failure, fall back to deep audit (fail-safe).
                triage = {
                    "verdict": "REVIEW_NEEDED",
                    "risk_level": "Medium",
                    "reason": f"Triage error, escalated to deep audit: {e}",
                }
            triage_results[i] = triage

            if triage.get("verdict", "").upper() == "COMPLIANT":
                record = _build_record(i)
                finalized[i] = record
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, record, False)
            else:
                df = deep_pool.submit(
                    _deep_call,
                    audit_chunks[i].page_content,
                    contexts[i],
                )
                deep_futs[df] = i

        # Drain layer-2 deep audits.
        for fut in as_completed(deep_futs):
            i = deep_futs[fut]
            try:
                deep_results[i] = fut.result()
            except Exception as e:
                deep_results[i] = f"Critical Error: deep audit failed. {e}"
            record = _build_record(i)
            finalized[i] = record
            completed += 1
            if progress_callback:
                is_high = record["status"] == "High Risk"
                progress_callback(completed, total, record, is_high)
            if record["status"] == "High Risk":
                print(
                    f"🔴 High Risk Found (Page {record['page_num']}):\n"
                    f"{record['audit_result'].strip()}\n"
                )
    finally:
        triage_pool.shutdown(wait=True)
        deep_pool.shutdown(wait=True)

    # Reassemble in original document order.
    report = [finalized[i] for i in range(total) if i in finalized]

    deep_count = len(deep_results)
    print(
        f"✅ Two-layer audit complete: {total} clauses triaged, "
        f"{deep_count} escalated to {DEEP_MODEL} "
        f"({(deep_count / total * 100) if total else 0:.0f}% of total)."
    )

    # Save Report
    report_file = report_output_path or "audit_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4)

    print(f"✅ Full report saved to {os.path.abspath(report_file)}")
    return report


# =====================================================================
# Main Header
# =====================================================================
def main() -> None:
    banner = textwrap.dedent("""\
    ╔══════════════════════════════════════════════════════════════╗
    ║        DPDP Act 2023 – Legal Compliance Auditor             ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    print(banner)

    # Check if we need to ingest base material
    db_exists = os.path.isdir(DB_DIR) and len(os.listdir(DB_DIR)) > 0
    store_exists = os.path.isfile(STORE_PATH)
    
    needs_ingestion = not (db_exists and store_exists)
    
    if needs_ingestion:
        print("\n🚀  First run (or missing DB) – ingesting target DPDP Act PDFs...")
    else:
        print("\n✅  Existing persistent storage found. Loading...")

    retriever = get_retriever(ingest=needs_ingestion)
    
    # Menu Loop
    while True:
        print("\nWhat would you like to do?")
        print("  1) Interactive Q&A Mode")
        print("  2) Run Compliance Audit against a Document")
        print("  3) Exit")
        
        choice = input("Select an option (1/2/3): ").strip()
        
        if choice == '1':
            chain = build_chain(retriever)
            interactive_loop(chain)
        elif choice == '2':
            run_compliance_audit(retriever)
        elif choice in {'3', 'quit', 'exit'}:
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    import logging
    logging.getLogger("langchain.text_splitter").setLevel(logging.ERROR)
    main()

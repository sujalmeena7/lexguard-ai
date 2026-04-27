"""
DPDP Act 2023 – Legal Compliance Auditor (RAG System)
=====================================================
Uses a 2-tier ParentDocumentRetriever for context-aware extraction,
persists parent documents to disk, and introduces an automated
"Audit Engine" mode.
"""

import os
import sys
import glob
import json
import textwrap
import streamlit as st
from typing import Optional

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
GEMINI_MODEL  = "gemini-1.5-pro"
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


def index_user_document(user_id: str, user_doc_path: str) -> int:
    """Index user document chunks with user_id metadata for isolated retrieval."""
    user_docs = _load_user_document(user_doc_path)
    if not user_docs:
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    user_chunks = splitter.split_documents(user_docs)
    for chunk in user_chunks:
        chunk.metadata = {
            **chunk.metadata,
            "user_id": user_id,
            "source_path": os.path.basename(user_doc_path),
        }

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = Chroma(
        persist_directory=WORKSPACE_DB_DIR,
        embedding_function=embeddings,
        collection_name=WORKSPACE_COLLECTION,
    )
    vectorstore.add_documents(user_chunks)
    return len(user_chunks)


def get_user_workspace_retriever(user_id: str, k: int = 4):
    """Create a user-scoped retriever that filters vectors by user_id."""
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vectorstore = Chroma(
        persist_directory=WORKSPACE_DB_DIR,
        embedding_function=embeddings,
        collection_name=WORKSPACE_COLLECTION,
    )
    return vectorstore.as_retriever(
        search_kwargs={"k": k, "filter": {"user_id": user_id}}
    )


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

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=google_key, temperature=0)
    
    print(f"\n🔍 Analyzing {len(audit_chunks)} sections of the document...\n")
    report = []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def get_audit_completion(user_text, context):
        return llm.invoke(AUDIT_PROMPT.format(user_text=user_text, context=context))

    for idx, chunk in enumerate(audit_chunks):
        # 1. Retrieve legal context
        legal_docs = retriever.invoke(chunk.page_content)
        context_str = "\n\n".join([d.page_content for d in legal_docs])

        # Optional: retrieve user workspace context strictly scoped to this user.
        if user_workspace_retriever is not None:
            user_workspace_docs = user_workspace_retriever.invoke(chunk.page_content)
            if user_workspace_docs:
                workspace_context = "\n\n".join(d.page_content for d in user_workspace_docs)
                context_str = (
                    f"{context_str}\n\nUser Workspace Context (isolated):\n{workspace_context}"
                )
        
        # 2. Predict Compliance with Retry Logic
        try:
            raw_response = get_audit_completion(chunk.page_content, context_str)
            response = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
        except Exception as e:
            response = f"Critical Error: Failed after multiple attempts. {e}"
            
        is_high_risk = "Non-Compliant" in response

        record = {
            "clause_id": idx + 1,
            "page_num": chunk.metadata.get("page", 0) + 1,
            "clause_text": chunk.page_content,
            "audit_result": response,
            "status": "High Risk" if is_high_risk else "Reviewed"
        }
        report.append(record)
        
        if is_high_risk:
            print(f"🔴 High Risk Found (Page {record['page_num']}):\n{response.strip()}\n")
            
        if progress_callback:
            progress_callback(idx + 1, len(audit_chunks), record, is_high_risk)
            
    # Save Report
    report_file = report_output_path or "audit_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4)
        
    print(f"✅ Audit complete. Full report saved to {os.path.abspath(report_file)}")
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

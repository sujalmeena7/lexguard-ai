from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from auth_utils import get_supabase_client


AUDIT_LOGS_TABLE = "audit_logs"
UPLOADED_FILES_TABLE = "uploaded_files"


SCHEMA_REFERENCE_SQL = """
-- Run in Supabase SQL Editor (example schema)
create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  source_name text not null,
  source_type text not null,
  summary text,
  findings_json jsonb not null,
  metrics_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.uploaded_files (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  filename text not null,
  storage_path text not null,
  mime_type text,
  size_bytes bigint,
  created_at timestamptz not null default now()
);

-- Enable RLS and enforce per-user access.
alter table public.audit_logs enable row level security;
alter table public.uploaded_files enable row level security;

create policy "audit_logs_select_own" on public.audit_logs
for select using (auth.uid() = user_id);
create policy "audit_logs_insert_own" on public.audit_logs
for insert with check (auth.uid() = user_id);
create policy "audit_logs_delete_own" on public.audit_logs
for delete using (auth.uid() = user_id);

create policy "uploaded_files_select_own" on public.uploaded_files
for select using (auth.uid() = user_id);
create policy "uploaded_files_insert_own" on public.uploaded_files
for insert with check (auth.uid() = user_id);
create policy "uploaded_files_delete_own" on public.uploaded_files
for delete using (auth.uid() = user_id);
""".strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_uploaded_file(
    user_id: str,
    filename: str,
    storage_path: str,
    size_bytes: int,
    mime_type: str,
) -> Tuple[bool, str, Optional[str]]:
    client = get_supabase_client()
    if client is None:
        return False, "Supabase client is not configured.", None

    payload = {
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "size_bytes": size_bytes,
        "mime_type": mime_type,
        "created_at": _now_iso(),
    }

    try:
        response = client.table(UPLOADED_FILES_TABLE).insert(payload).execute()
        inserted = response.data[0] if response.data else {}
        return True, "Uploaded file metadata saved.", inserted.get("id")
    except Exception as exc:
        return False, f"Failed to save uploaded file metadata: {exc}", None


def save_audit_log(
    user_id: str,
    source_name: str,
    source_type: str,
    summary: str,
    findings_json: List[Dict],
    metrics_json: Dict,
) -> Tuple[bool, str, Optional[str]]:
    client = get_supabase_client()
    if client is None:
        return False, "Supabase client is not configured.", None

    payload = {
        "user_id": user_id,
        "source_name": source_name,
        "source_type": source_type,
        "summary": summary,
        "findings_json": findings_json,
        "metrics_json": metrics_json,
        "created_at": _now_iso(),
    }

    try:
        response = client.table(AUDIT_LOGS_TABLE).insert(payload).execute()
        inserted = response.data[0] if response.data else {}
        return True, "Audit log saved.", inserted.get("id")
    except Exception as exc:
        return False, f"Failed to save audit log: {exc}", None


def fetch_user_audits(user_id: str, limit: int = 50) -> Tuple[bool, str, List[Dict]]:
    client = get_supabase_client()
    if client is None:
        return False, "Supabase client is not configured.", []

    try:
        response = (
            client.table(AUDIT_LOGS_TABLE)
            .select("id, source_name, source_type, summary, metrics_json, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return True, "Fetched user audit history.", response.data or []
    except Exception as exc:
        return False, f"Failed to fetch audit history: {exc}", []


def delete_user_audit(user_id: str, audit_id: str) -> Tuple[bool, str]:
    client = get_supabase_client()
    if client is None:
        return False, "Supabase client is not configured."

    try:
        (
            client.table(AUDIT_LOGS_TABLE)
            .delete()
            .eq("id", audit_id)
            .eq("user_id", user_id)
            .execute()
        )
        return True, "Audit log deleted."
    except Exception as exc:
        return False, f"Failed to delete audit log: {exc}"

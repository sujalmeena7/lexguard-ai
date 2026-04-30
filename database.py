from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from auth_utils import get_supabase_client


AUDIT_LOGS_TABLE = "audit_logs"
UPLOADED_FILES_TABLE = "uploaded_files"
USER_PROFILES_TABLE = "user_profiles"
SECURITY_LOGS_TABLE = "security_logs"


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

create table if not exists public.user_profiles (
  id uuid primary key references auth.users on delete cascade,
  email text,
  credits int default 5,
  is_premium boolean default false,
  updated_at timestamptz default now()
);

create table if not exists public.security_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  event_type text not null,
  severity text default 'INFO',
  description text,
  ip_address text,
  metadata jsonb,
  created_at timestamptz default now()
);

-- Enable RLS and enforce per-user access.
alter table public.audit_logs enable row level security;
alter table public.uploaded_files enable row level security;
alter table public.user_profiles enable row level security;
alter table public.security_logs enable row level security;

-- Policies
create policy "audit_logs_select_own" on public.audit_logs for select using (auth.uid() = user_id);
create policy "audit_logs_insert_own" on public.audit_logs for insert with check (auth.uid() = user_id);
create policy "audit_logs_delete_own" on public.audit_logs for delete using (auth.uid() = user_id);

create policy "uploaded_files_select_own" on public.uploaded_files for select using (auth.uid() = user_id);
create policy "uploaded_files_insert_own" on public.uploaded_files for insert with check (auth.uid() = user_id);

create policy "user_profiles_select_own" on public.user_profiles for select using (auth.uid() = id);
create policy "user_profiles_insert_own" on public.user_profiles for insert with check (auth.uid() = id);
create policy "user_profiles_update_own" on public.user_profiles for update using (auth.uid() = id);

create policy "security_logs_insert_auth" on public.security_logs for insert with check (auth.role() = 'authenticated');
create policy "security_logs_select_own" on public.security_logs for select using (auth.uid() = user_id);

-- 7. Atomic Credit Deduction Function
create or replace function deduct_credit_v1(target_user_id uuid)
returns int as $$
declare
  updated_credits int;
begin
  update user_profiles
  set credits = credits - 1
  where id = target_user_id and credits > 0
  returning credits into updated_credits;
  
  return updated_credits;
end;
$$ language plpgsql security definer;
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


def fetch_user_uploaded_files(user_id: str, limit: int = 50) -> Tuple[bool, str, List[Dict]]:
    client = get_supabase_client()
    if client is None:
        return False, "Supabase client is not configured.", []

    try:
        response = (
            client.table(UPLOADED_FILES_TABLE)
            .select("id, filename, storage_path, mime_type, size_bytes, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return True, "Fetched user uploaded file history.", response.data or []
    except Exception as exc:
        return False, f"Failed to fetch uploaded file history: {exc}", []


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
 
 
def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    severity: str = "INFO",
    description: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> None:
    client = get_supabase_client()
    if client is None:
        return

    payload = {
        "event_type": event_type,
        "user_id": user_id,
        "severity": severity,
        "description": description,
        "metadata": metadata,
        "created_at": _now_iso(),
    }
    try:
        client.table(SECURITY_LOGS_TABLE).insert(payload).execute()
    except Exception as exc:
        print(f"Failed to log security event: {exc}")


def get_or_create_user_profile(user_id: str, email: str) -> Dict:
    client = get_supabase_client()
    if client is None:
        return {}

    try:
        # First, try to fetch the existing profile
        response = client.table(USER_PROFILES_TABLE).select("*").eq("id", user_id).execute()
        if response.data:
            existing_profile = response.data[0]
            # If email is provided and different, update it
            if email and email.strip() and existing_profile.get("email") != email.strip():
                client.table(USER_PROFILES_TABLE).update({"email": email.strip()}).eq("id", user_id).execute()
                existing_profile["email"] = email.strip()
            return existing_profile

        # If not found, create new profile with defaults
        new_profile = {"id": user_id, "credits": 5, "is_premium": False}
        if email and email.strip():
            new_profile["email"] = email.strip()

        response = client.table(USER_PROFILES_TABLE).insert(new_profile).execute()
        return response.data[0] if response.data else {}
    except Exception as exc:
        print(f"Failed to get/create user profile: {exc}")
        return {}


def deduct_user_credit(user_id: str) -> Tuple[bool, int]:
    client = get_supabase_client()
    if client is None:
        return False, 0

    try:
        # Use RPC for atomic decrement to prevent race conditions
        response = client.rpc("deduct_credit_v1", {"target_user_id": user_id}).execute()
        if response.data is not None:
            return True, response.data
        
        return False, 0
    except Exception as exc:
        # Fallback for if the RPC isn't installed yet
        print(f"Atomic credit deduction failed (RPC might be missing): {exc}")
        return False, 0


def update_user_premium_status(user_id: str, is_premium: bool) -> bool:
    client = get_supabase_client()
    if client is None:
        return False

    try:
        client.table(USER_PROFILES_TABLE).update({"is_premium": is_premium}).eq("id", user_id).execute()
        return True
    except Exception as exc:
        print(f"Failed to update premium status: {exc}")
        return False


def add_user_credits(user_id: str, amount: int) -> Tuple[bool, int]:
    client = get_supabase_client()
    if client is None:
        return False, 0

    try:
        # Fetch current balance
        response = client.table(USER_PROFILES_TABLE).select("credits").eq("id", user_id).execute()
        
        if not response.data:
            # Fallback: ensure profile exists and try again
            profile = get_or_create_user_profile(user_id, "")
            if not profile:
                return False, 0
            current_credits = profile.get("credits", 0)
        else:
            current_credits = response.data[0].get("credits", 0)
            
        new_credits = min(current_credits + amount, 10)

        # Update balance
        client.table(USER_PROFILES_TABLE).update({"credits": new_credits}).eq("id", user_id).execute()
        return True, new_credits
    except Exception as exc:
        print(f"Failed to add user credits: {exc}")
        return False, 0


def check_rate_limit(event_type: str, user_id: Optional[str] = None, limit: int = 5, window_minutes: int = 15) -> bool:
    """Returns True if the rate limit is NOT exceeded."""
    client = get_supabase_client()
    if client is None:
        return True

    since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
    try:
        query = client.table(SECURITY_LOGS_TABLE).select("id", count="exact").eq("event_type", event_type).gt("created_at", since)
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.execute()
        count = response.count if hasattr(response, 'count') else len(response.data or [])
        return count < limit
    except Exception as exc:
        print(f"Rate limit check failed (Fail-closed for security): {exc}")
        return False

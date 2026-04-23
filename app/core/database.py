from supabase import create_client, Client
from app.core.config import settings

# Standard client (uses anon key - respects row-level security)
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# Service client (bypasses RLS - use only in trusted server-side operations)
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_key)

import random
import string
from typing import Optional

from app.core.database import supabase_admin


def generate_session_code(length: int = 6) -> str:
    """Generate a short uppercase alphanumeric code e.g. 'K7X2MQ'"""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


async def create_session(
    host_id: str,
    name: str,
    latitude: float,
    longitude: float,
    radius_meters: int = 2000,
) -> dict:
    code = generate_session_code()

    # Ensure code is unique (rare collision, but worth checking)
    while True:
        existing = (
            supabase_admin.table("sessions")
            .select("id")
            .eq("code", code)
            .eq("status", "waiting")
            .execute()
        )
        if not existing.data:
            break
        code = generate_session_code()

    result = (
        supabase_admin.table("sessions")
        .insert({
            "host_id": host_id,
            "name": name,
            "code": code,
            "latitude": latitude,
            "longitude": longitude,
            "radius_meters": radius_meters,
            "status": "waiting",
        })
        .execute()
    )

    session = result.data[0]

    # Add host as first member
    supabase_admin.table("session_members").insert({
        "session_id": session["id"],
        "user_id": host_id,
    }).execute()

    return session


async def get_session_by_code(code: str) -> Optional[dict]:
    result = (
        supabase_admin.table("sessions")
        .select("*")
        .eq("code", code.upper())
        .eq("status", "waiting")
        .execute()
    )
    return result.data[0] if result.data else None


async def join_session(session_id: str, user_id: str) -> bool:
    # Check if already a member
    existing = (
        supabase_admin.table("session_members")
        .select("id")
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if existing.data:
        return True  # Already in, that's fine

    supabase_admin.table("session_members").insert({
        "session_id": session_id,
        "user_id": user_id,
    }).execute()
    return True


async def get_session_member_count(session_id: str) -> int:
    result = (
        supabase_admin.table("session_members")
        .select("id", count="exact")
        .eq("session_id", session_id)
        .execute()
    )
    return result.count or 0


async def get_session_member_preferences(session_id: str) -> list:
    """Fetch all members' dietary preferences for a session."""
    result = (
        supabase_admin.table("session_members")
        .select("user_id, users(preferences)")
        .eq("session_id", session_id)
        .execute()
    )
    prefs = []
    for row in result.data or []:
        user_data = row.get("users") or {}
        raw_prefs = user_data.get("preferences") or {}
        if raw_prefs:
            from app.schemas.schemas import DietaryPreferences
            prefs.append(DietaryPreferences(**raw_prefs))
    return prefs


async def set_session_status(session_id: str, status: str) -> None:
    supabase_admin.table("sessions").update({"status": status}).eq("id", session_id).execute()

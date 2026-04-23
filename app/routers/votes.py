from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.schemas.schemas import VoteRequest, VoteResult, Restaurant
from app.core.security import get_current_user
from app.core.database import supabase_admin

router = APIRouter(prefix="/votes", tags=["votes"])


@router.post("", status_code=201)
async def submit_vote(
    body: VoteRequest,
    current_user: dict = Depends(get_current_user),
):
    # Verify session is in swiping state
    session_result = (
        supabase_admin.table("sessions")
        .select("status")
        .eq("id", body.session_id)
        .execute()
    )
    if not session_result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_result.data[0]["status"] != "swiping":
        raise HTTPException(status_code=400, detail="Session is not in swiping state")

    # Upsert vote (allows changing mind)
    supabase_admin.table("votes").upsert(
        {
            "session_id": body.session_id,
            "user_id": current_user["id"],
            "restaurant_id": body.restaurant_id,
            "direction": body.direction,
        },
        on_conflict="session_id,user_id,restaurant_id",
    ).execute()

    # Check if all members have finished swiping
    await _check_all_done(body.session_id, current_user["id"])

    return {"ok": True}


@router.post("/{session_id}/done", status_code=200)
async def mark_done(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """User signals they have finished swiping their deck."""
    supabase_admin.table("session_members").update({"done_swiping": True}).match({
        "session_id": session_id,
        "user_id": current_user["id"],
    }).execute()

    await _check_all_done(session_id, current_user["id"])
    return {"ok": True}


@router.get("/{session_id}/results", response_model=List[VoteResult])
async def get_results(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    session_result = supabase_admin.table("sessions").select("status").eq("id", session_id).execute()
    if not session_result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Allow viewing results once swiping or results state
    if session_result.data[0]["status"] == "waiting":
        raise HTTPException(status_code=400, detail="Session hasn't started yet")

    # Get all restaurants for this session
    restaurants_result = (
        supabase_admin.table("session_restaurants")
        .select("restaurant_id, restaurant_data")
        .eq("session_id", session_id)
        .execute()
    )
    restaurants_by_id = {
        row["restaurant_id"]: Restaurant(**row["restaurant_data"])
        for row in restaurants_result.data or []
    }

    # Get total number of voters
    members_result = (
        supabase_admin.table("session_members")
        .select("id", count="exact")
        .eq("session_id", session_id)
        .execute()
    )
    total_voters = members_result.count or 1

    # Aggregate right-swipes per restaurant
    votes_result = (
        supabase_admin.table("votes")
        .select("restaurant_id, direction")
        .eq("session_id", session_id)
        .eq("direction", "right")
        .execute()
    )

    tally: dict[str, int] = {}
    for vote in votes_result.data or []:
        rid = vote["restaurant_id"]
        tally[rid] = tally.get(rid, 0) + 1

    # Build ranked results (only restaurants with at least 1 right swipe)
    results = []
    for rid, count in tally.items():
        restaurant = restaurants_by_id.get(rid)
        if restaurant:
            results.append(VoteResult(
                restaurant=restaurant,
                right_swipes=count,
                total_voters=total_voters,
                score=round(count / total_voters, 2),
            ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results


async def _check_all_done(session_id: str, user_id: str) -> None:
    """If all members are done swiping, move session to 'results' state."""
    members_result = (
        supabase_admin.table("session_members")
        .select("done_swiping")
        .eq("session_id", session_id)
        .execute()
    )
    members = members_result.data or []
    if members and all(m.get("done_swiping") for m in members):
        supabase_admin.table("sessions").update({"status": "results"}).eq("id", session_id).execute()

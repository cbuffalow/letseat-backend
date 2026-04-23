from fastapi import APIRouter, HTTPException, Depends

from app.schemas.schemas import (
    CreateSessionRequest, JoinSessionRequest,
    SessionResponse, Restaurant,
)
from app.core.security import get_current_user
from app.services import session as session_svc
from app.services.yelp import fetch_restaurants

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    session = await session_svc.create_session(
        host_id=current_user["id"],
        name=body.name,
        latitude=body.latitude,
        longitude=body.longitude,
        radius_meters=body.radius_meters,
    )
    count = await session_svc.get_session_member_count(session["id"])
    return SessionResponse(**session, member_count=count)


@router.post("/join", response_model=SessionResponse)
async def join_session(
    body: JoinSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    session = await session_svc.get_session_by_code(body.code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or already started")

    await session_svc.join_session(session["id"], current_user["id"])
    count = await session_svc.get_session_member_count(session["id"])
    return SessionResponse(**session, member_count=count)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    from app.core.database import supabase_admin
    result = supabase_admin.table("sessions").select("*").eq("id", session_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    session = result.data[0]
    count = await session_svc.get_session_member_count(session_id)
    return SessionResponse(**session, member_count=count)


@router.post("/{session_id}/start", response_model=dict)
async def start_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Host starts the session — fetches restaurants and moves status to 'swiping'."""
    from app.core.database import supabase_admin

    result = supabase_admin.table("sessions").select("*").eq("id", session_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    session = result.data[0]

    if session["host_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Only the host can start the session")

    if session["status"] != "waiting":
        raise HTTPException(status_code=400, detail="Session already started")

    # Fetch group preferences and get restaurants from Yelp
    prefs = await session_svc.get_session_member_preferences(session_id)
    restaurants = await fetch_restaurants(
        lat=session["latitude"],
        lng=session["longitude"],
        radius=session["radius_meters"],
        group_preferences=prefs,
        limit=20,
    )

    if not restaurants:
        raise HTTPException(status_code=404, detail="No restaurants found for this group's preferences")

    # Cache restaurants for this session
    for r in restaurants:
        supabase_admin.table("session_restaurants").upsert({
            "session_id": session_id,
            "restaurant_id": r.id,
            "restaurant_data": r.model_dump(),
        }).execute()

    await session_svc.set_session_status(session_id, "swiping")

    return {"status": "swiping", "restaurant_count": len(restaurants)}


@router.get("/{session_id}/restaurants", response_model=list[Restaurant])
async def get_session_restaurants(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Returns the deck of restaurants for swiping."""
    from app.core.database import supabase_admin

    result = (
        supabase_admin.table("session_restaurants")
        .select("restaurant_data")
        .eq("session_id", session_id)
        .execute()
    )

    return [Restaurant(**row["restaurant_data"]) for row in result.data or []]

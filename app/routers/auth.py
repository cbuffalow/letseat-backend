from fastapi import APIRouter, HTTPException, Depends, status

from app.schemas.schemas import (
    SignupRequest, LoginRequest, TokenResponse,
    UserProfile, ProfileUpdate, DietaryPreferences,
)
from app.core.security import (
    hash_password, verify_password,
    create_access_token, get_current_user,
)
from app.core.database import supabase_admin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    # Check email not already registered
    existing = (
        supabase_admin.table("users")
        .select("id")
        .eq("email", body.email)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed = hash_password(body.password)

    result = (
        supabase_admin.table("users")
        .insert({
            "email": body.email,
            "password_hash": hashed,
            "display_name": body.display_name,
            "preferences": DietaryPreferences().model_dump(),
        })
        .execute()
    )

    user = result.data[0]
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    result = (
        supabase_admin.table("users")
        .select("*")
        .eq("email", body.email)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = result.data[0]

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)):
    result = (
        supabase_admin.table("users")
        .select("*")
        .eq("id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    u = result.data[0]
    return UserProfile(
        id=u["id"],
        email=u["email"],
        display_name=u["display_name"],
        preferences=DietaryPreferences(**(u.get("preferences") or {})),
    )


@router.patch("/me", response_model=UserProfile)
async def update_profile(
    body: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    updates = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.preferences is not None:
        updates["preferences"] = body.preferences.model_dump()

    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")

    supabase_admin.table("users").update(updates).eq("id", current_user["id"]).execute()

    return await get_me(current_user)

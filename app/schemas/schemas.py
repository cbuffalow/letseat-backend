from pydantic import BaseModel, EmailStr
from typing import Optional, List


# ── Auth ──────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── User Profile ──────────────────────────────────────
class DietaryPreferences(BaseModel):
    restrictions: List[str] = []   # e.g. ["vegetarian", "gluten-free"]
    cuisines_liked: List[str] = [] # e.g. ["italian", "thai"]
    cuisines_disliked: List[str] = []
    price_range: List[int] = [1, 2, 3, 4]  # Yelp price tiers 1-4


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    preferences: Optional[DietaryPreferences] = None


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    preferences: DietaryPreferences


# ── Sessions ──────────────────────────────────────────
class CreateSessionRequest(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: int = 2000


class JoinSessionRequest(BaseModel):
    code: str  # 6-character alphanumeric code


class SessionResponse(BaseModel):
    id: str
    name: str
    code: str
    host_id: str
    latitude: float
    longitude: float
    radius_meters: int
    status: str  # "waiting" | "swiping" | "results"
    member_count: int


# ── Restaurants ───────────────────────────────────────
class Restaurant(BaseModel):
    id: str          # Yelp business ID
    name: str
    image_url: Optional[str]
    url: str
    rating: float
    review_count: int
    price: Optional[str]  # "$", "$$", etc.
    categories: List[str]
    distance_meters: float
    address: str
    latitude: float
    longitude: float


# ── Votes ─────────────────────────────────────────────
class VoteRequest(BaseModel):
    session_id: str
    restaurant_id: str
    direction: str  # "right" (like) or "left" (pass)


class VoteResult(BaseModel):
    restaurant: Restaurant
    right_swipes: int
    total_voters: int
    score: float  # right_swipes / total_voters

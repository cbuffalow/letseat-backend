import httpx
from typing import List, Optional
from app.core.config import settings
from app.schemas.schemas import Restaurant, DietaryPreferences

YELP_BASE = "https://api.yelp.com/v3"

# Maps dietary restriction labels to Yelp category aliases
RESTRICTION_CATEGORY_MAP = {
    "vegetarian": "vegetarian",
    "vegan": "vegan",
    "gluten-free": "gluten_free",
    "halal": "halal",
    "kosher": "kosher",
}


def _build_headers() -> dict:
    return {"Authorization": f"Bearer {settings.yelp_api_key}"}


def _merge_group_preferences(prefs_list: List[DietaryPreferences]) -> dict:
    """
    Merge preferences from all group members into a single Yelp query config.

    Rules:
    - Hard restrictions (dietary): union — if anyone needs it, everyone respects it
    - Cuisines liked: intersection — only suggest if the whole group likes it
      (falls back to no cuisine filter if there's no overlap)
    - Cuisines disliked: union — exclude if anyone dislikes it
    - Price range: intersection of acceptable tiers across all members
    """
    if not prefs_list:
        return {}

    # Hard dietary restrictions — union
    all_restrictions = set()
    for p in prefs_list:
        all_restrictions.update(p.restrictions)

    # Cuisines liked — intersection (strict), fall back to empty (no filter)
    liked_sets = [set(p.cuisines_liked) for p in prefs_list if p.cuisines_liked]
    if liked_sets:
        liked_intersection = liked_sets[0].intersection(*liked_sets[1:])
    else:
        liked_intersection = set()

    # Cuisines disliked — union
    disliked = set()
    for p in prefs_list:
        disliked.update(p.cuisines_disliked)

    # Price range — intersection of all members' acceptable tiers
    price_sets = [set(p.price_range) for p in prefs_list]
    shared_prices = price_sets[0].intersection(*price_sets[1:]) if price_sets else {1, 2, 3, 4}

    return {
        "restrictions": list(all_restrictions),
        "cuisines_liked": list(liked_intersection - disliked),
        "price_range": sorted(shared_prices),
    }


def _build_yelp_params(
    lat: float,
    lng: float,
    radius: int,
    merged_prefs: dict,
    limit: int = 40,
) -> dict:
    params = {
        "latitude": lat,
        "longitude": lng,
        "radius": min(radius, 40000),  # Yelp max is 40km
        "limit": limit,
        "sort_by": "best_match",
        "categories": "restaurants,food",
    }

    # Map dietary restrictions to Yelp category aliases
    restriction_categories = [
        RESTRICTION_CATEGORY_MAP[r]
        for r in merged_prefs.get("restrictions", [])
        if r in RESTRICTION_CATEGORY_MAP
    ]
    liked_cuisines = merged_prefs.get("cuisines_liked", [])

    all_categories = restriction_categories + liked_cuisines
    if all_categories:
        params["categories"] = ",".join(all_categories)

    price_range = merged_prefs.get("price_range", [])
    if price_range:
        params["price"] = ",".join(str(p) for p in price_range)

    return params


def _parse_business(biz: dict) -> Optional[Restaurant]:
    try:
        return Restaurant(
            id=biz["id"],
            name=biz["name"],
            image_url=biz.get("image_url"),
            url=biz.get("url", ""),
            rating=biz.get("rating", 0),
            review_count=biz.get("review_count", 0),
            price=biz.get("price"),
            categories=[c["title"] for c in biz.get("categories", [])],
            distance_meters=biz.get("distance", 0),
            address=", ".join(biz.get("location", {}).get("display_address", [])),
            latitude=biz.get("coordinates", {}).get("latitude", 0),
            longitude=biz.get("coordinates", {}).get("longitude", 0),
        )
    except Exception:
        return None


async def fetch_restaurants(
    lat: float,
    lng: float,
    radius: int,
    group_preferences: List[DietaryPreferences],
    limit: int = 20,
) -> List[Restaurant]:
    merged = _merge_group_preferences(group_preferences)
    params = _build_yelp_params(lat, lng, radius, merged, limit=40)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{YELP_BASE}/businesses/search",
            headers=_build_headers(),
            params=params,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    businesses = data.get("businesses", [])

    # Filter out permanently closed
    businesses = [b for b in businesses if not b.get("is_closed", False)]

    # Filter out any disliked cuisines
    disliked = set(merged.get("cuisines_liked", []))  # already filtered above, but belt+suspenders
    disliked_raw = set()
    for p in group_preferences:
        disliked_raw.update(p.cuisines_disliked)

    def has_disliked_category(biz: dict) -> bool:
        cats = {c["alias"] for c in biz.get("categories", [])}
        cats |= {c["title"].lower() for c in biz.get("categories", [])}
        return bool(cats & disliked_raw)

    businesses = [b for b in businesses if not has_disliked_category(b)]

    restaurants = [_parse_business(b) for b in businesses]
    restaurants = [r for r in restaurants if r is not None]

    return restaurants[:limit]

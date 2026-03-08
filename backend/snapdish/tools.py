"""
Store, nutrition, and grocery helpers.

Production integrations:
  - Nutrition data: USDA FoodData Central (via food_api + meal_repository)
  - Nearby stores: Google Places API (key: GOOGLE_PLACES_API_KEY in secrets)
  - Grocery list: DB-aware, capped for scalability
  - Food alternatives: meal_repository (DB + external food APIs)
"""

from __future__ import annotations

from .config import get_logger, get_secret
from .schemas import GeoLocation, GroceryItem, NutritionEstimate, StoreSuggestion

logger = get_logger(__name__)

# Guardrails: cap list sizes for scalability
MAX_GROCERY_ITEMS = 200
MAX_STORE_RESULTS = 10


def find_nearby_stores(location: GeoLocation | None) -> list[StoreSuggestion]:
    """
    Return nearby store suggestions.

    Primary:  Google Places Nearby Search (GOOGLE_PLACES_API_KEY in AWS Secrets).
    Fallback: OpenAI web_search with allowed_domains food/grocery guardrail — uses
              OPENAI_API_KEY already in AWS Secrets, no extra key needed.

    The OpenAI fallback uses web_search with allowed_domains restricting results to
    grocery and food retail domains (same guardrail as voice_agent search).
    """
    if location is None:
        return []

    api_key = get_secret("GOOGLE_PLACES_API_KEY")
    if not api_key:
        logger.info(
            "find_nearby_stores_no_google_key",
            extra={"detail": "Falling back to OpenAI web search for nearby stores"},
        )
        return _find_nearby_stores_openai_fallback(location)

    from .cache import TTL_FOOD_SEARCH, cache_get, cache_set

    ck = f"{location.lat:.4f},{location.lng:.4f}"
    cached = cache_get("stores", ck)
    if cached:
        return [StoreSuggestion(**s) for s in cached]

    try:
        import httpx

        params = {
            "location": f"{location.lat},{location.lng}",
            "radius": 3000,
            "type": "grocery_or_supermarket",
            "key": api_key,
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        stores: list[StoreSuggestion] = []
        for place in (data.get("results") or [])[:MAX_STORE_RESULTS]:
            geometry = place.get("geometry") or {}
            loc = geometry.get("location") or {}
            lat2 = loc.get("lat", location.lat)
            lng2 = loc.get("lng", location.lng)
            distance_km = _haversine_km(location.lat, location.lng, lat2, lng2)
            stores.append(
                StoreSuggestion(
                    name=place.get("name") or "Unknown",
                    address=place.get("vicinity"),
                    distance_km=round(distance_km, 2),
                )
            )

        cache_set("stores", ck, [s.model_dump() for s in stores], TTL_FOOD_SEARCH)
        logger.info(
            "find_nearby_stores_ok",
            extra={"lat": location.lat, "lng": location.lng, "results": len(stores)},
        )
        return stores

    except Exception as exc:
        logger.warning("find_nearby_stores_google_failed", extra={"error": str(exc)})
        # Google Places failed — try OpenAI web search as fallback
        return _find_nearby_stores_openai_fallback(location)


def _find_nearby_stores_openai_fallback(location: GeoLocation) -> list[StoreSuggestion]:
    """
    OpenAI web_search fallback for nearby grocery stores.
    Uses web_search with allowed_domains (grocery sites only) — guardrail enforced at
    OpenAI API level. All traffic via https://api.openai.com (OPENAI_API_KEY from AWS).
    Docs: https://developers.openai.com/api/docs/guides/tools-web-search#domain-filtering
    """
    _GROCERY_DOMAINS = [
        "instacart.com", "wholefoodsmarket.com", "kroger.com", "walmart.com",
        "target.com", "ocado.com", "waitrose.com", "sainsburys.co.uk",
        "tesco.com", "asda.com", "marksandspencer.com", "aldi.co.uk",
        "aldi.com", "lidl.co.uk", "morrisons.com", "coop.co.uk",
        "iceland.co.uk", "costco.com", "trader joes.com", "heb.com",
        "publix.com", "safeway.com", "albertsons.com", "wegmans.com",
    ]
    try:
        from .openai_client import get_client
        from .config import get_env
        client = get_client()
        model = get_env("SNAPDISH_SEARCH_MODEL") or get_secret("SNAPDISH_SEARCH_MODEL") or "gpt-4o-mini"
        response = client.responses.create(
            model=model,
            tools=[{
                "type": "web_search",
                "filters": {"allowed_domains": _GROCERY_DOMAINS},
            }],
            input=(
                f"Find grocery stores and supermarkets near latitude {location.lat:.4f}, "
                f"longitude {location.lng:.4f}. List store names and their approximate "
                "distance. Focus only on food grocery retailers."
            ),
            store=False,
        )
        text = (getattr(response, "output_text", None) or "").strip()
        if not text:
            return []
        # Parse bullet-style lines into StoreSuggestion objects
        stores: list[StoreSuggestion] = []
        for line in text.splitlines():
            line = line.strip().lstrip("•-*").strip()
            if line and len(line) > 3:
                stores.append(StoreSuggestion(name=line[:120], address=None, distance_km=None))
        stores = stores[:MAX_STORE_RESULTS]
        logger.info("find_nearby_stores_openai_fallback_ok", extra={"results": len(stores)})
        return stores
    except Exception as exc:
        logger.warning("find_nearby_stores_openai_fallback_failed", extra={"error": str(exc)})
        return []


def build_grocery_list(ingredients: list[str]) -> list[GroceryItem]:
    """Build grocery list from ingredient names. Capped at MAX_GROCERY_ITEMS for guardrails."""
    items: list[GroceryItem] = []
    for ingredient in ingredients[:MAX_GROCERY_ITEMS]:
        normalized = ingredient.strip()
        if normalized:
            items.append(GroceryItem(item=normalized))
    if len(ingredients) > MAX_GROCERY_ITEMS:
        logger.warning(
            "grocery_list_truncated",
            extra={"total": len(ingredients), "max": MAX_GROCERY_ITEMS},
        )
    return items


def estimate_nutrition(food_name: str) -> NutritionEstimate:
    """
    Fetch nutrition estimate.

    Primary:  USDA FoodData Central via meal_repository (USDA_FDC_API_KEY).
    Fallback: OpenAI structured output — asks the model for per-100g macros using
              its training knowledge. Uses OPENAI_API_KEY from AWS Secrets.
              All traffic via https://api.openai.com.
    """
    if not food_name or not food_name.strip():
        return _empty_nutrition()

    try:
        from .meal_repository import get_ingredient_nutrition

        result = get_ingredient_nutrition(food_name.strip())
        per_100g = result.get("per_100g") or {}
        if any(per_100g.values()):
            return NutritionEstimate(
                calories_kcal=_to_int(per_100g.get("calories_kcal")),
                protein_g=per_100g.get("protein_g"),
                carbs_g=per_100g.get("carbs_g"),
                fat_g=per_100g.get("fat_g"),
                disclaimer=(
                    "Estimates per 100 g from USDA FoodData Central. "
                    "Actual macros depend on preparation, portion, and variety."
                ),
            )
    except Exception as exc:
        logger.warning("estimate_nutrition_usda_failed", extra={"food": food_name, "error": str(exc)})

    # USDA lookup came back empty or failed — fall back to OpenAI
    return _estimate_nutrition_openai_fallback(food_name)


def _estimate_nutrition_openai_fallback(food_name: str) -> NutritionEstimate:
    """
    OpenAI fallback for nutrition estimation.
    Returns structured per-100g macros using the model's culinary knowledge.
    Uses OPENAI_API_KEY from AWS Secrets (https://api.openai.com, TLS verified).
    """
    try:
        import json
        from .openai_client import get_client
        from .config import get_env
        client = get_client()
        model = get_env("SNAPDISH_MODEL") or get_secret("SNAPDISH_MODEL") or "gpt-4o-mini"
        resp = client.responses.create(
            model=model,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "You are a nutrition database assistant. "
                        "Return ONLY a JSON object with keys: "
                        "calories_kcal (int), protein_g (float), carbs_g (float), fat_g (float). "
                        "Values are estimates per 100 g of the food. "
                        "No explanation, no markdown, JSON only."
                    ),
                },
                {"role": "user", "content": f"Nutrition per 100g for: {food_name}"},
            ],
            text={"format": {"type": "json_object"}},
            store=False,
            max_output_tokens=80,
        )
        text = (getattr(resp, "output_text", None) or "").strip()
        data = json.loads(text) if text else {}
        return NutritionEstimate(
            calories_kcal=_to_int(data.get("calories_kcal")),
            protein_g=data.get("protein_g"),
            carbs_g=data.get("carbs_g"),
            fat_g=data.get("fat_g"),
            disclaimer=(
                f"Estimated per 100 g via OpenAI ({model}). "
                "Actual macros depend on preparation and variety. "
                "For precise values, configure USDA_FDC_API_KEY."
            ),
        )
    except Exception as exc:
        logger.warning("estimate_nutrition_openai_fallback_failed", extra={"food": food_name, "error": str(exc)})
        return _empty_nutrition()


# Keep the old name as an alias for backward compatibility with existing callers
def estimate_nutrition_stub() -> NutritionEstimate:
    """
    Deprecated: prefer estimate_nutrition(food_name).
    Returns empty nutrition estimate with USDA integration note.
    """
    return _empty_nutrition()


def _empty_nutrition() -> NutritionEstimate:
    return NutritionEstimate(
        calories_kcal=None,
        protein_g=None,
        carbs_g=None,
        fat_g=None,
        disclaimer=(
            "Nutrition data unavailable for this item. "
            "For accurate macros, set USDA_FDC_API_KEY and ensure the ingredient name is specific."
        ),
    )


def _to_int(val) -> int | None:
    try:
        return int(float(val)) if val is not None else None
    except (TypeError, ValueError):
        return None


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Approximate great-circle distance in km between two GPS coordinates."""
    import math

    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

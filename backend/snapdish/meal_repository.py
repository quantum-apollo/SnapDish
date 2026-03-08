"""
Meal repository: query and cache meal alternatives from DB + external food APIs.

Query strategy (tiered for performance):
  1. Check cache (Redis/memory) — fastest.
  2. Check local DB (cached_meals table) — fast; avoids external API calls.
  3. Fetch from external food APIs (USDA FDC, Open Food Facts, Spoonacular) — may be slower.
  4. Persist external results back to DB + cache for future requests.

Dietary filtering is applied at every tier so only safe alternatives are returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .cache import TTL_MEAL_ALTERNATIVES, TTL_FOOD_NUTRITION, cache_get, cache_set
from .config import get_logger
from .food_api import FoodItem, search_all_food_sources

logger = get_logger(__name__)

_MAX_ALTERNATIVES = 8


@dataclass
class MealAlternative:
    name: str
    cuisine_tags: list[str] = field(default_factory=list)
    dietary_tags: list[str] = field(default_factory=list)
    calories_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    why_safe: str = ""
    image_url: str | None = None
    source: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "cuisine_tags": self.cuisine_tags,
            "dietary_tags": self.dietary_tags,
            "calories_kcal": self.calories_kcal,
            "protein_g": self.protein_g,
            "carbs_g": self.carbs_g,
            "fat_g": self.fat_g,
            "fiber_g": self.fiber_g,
            "why_safe": self.why_safe,
            "image_url": self.image_url,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Dietary tag → Spoonacular diet/intolerance labels mapping
# ---------------------------------------------------------------------------

_RESTRICTION_TO_SPOON = {
    "vegan": "vegan",
    "vegetarian": "vegetarian",
    "pescatarian": "pescatarian",
    "keto": "ketogenic",
    "paleo": "paleo",
    "low_fodmap": "fodmap friendly",
    "halal": None,   # Spoonacular doesn't have this; filter manually
    "kosher": None,
}

_ALLERGY_TO_SPOON_INTOLERANCE = {
    "peanuts": "peanut",
    "tree_nuts": "tree nut",
    "dairy": "dairy",
    "eggs": "egg",
    "wheat": "wheat",
    "gluten": "gluten",
    "soy": "soy",
    "fish": "seafood",
    "shellfish": "shellfish",
    "sesame": "sesame",
}


def _build_spoon_tags(allergy_tags: list[str], restriction_tags: list[str]) -> list[str]:
    tags: list[str] = []
    for r in restriction_tags:
        mapped = _RESTRICTION_TO_SPOON.get(r)
        if mapped:
            tags.append(mapped)
    return tags


def _item_safe_for_profile(
    item: FoodItem,
    allergy_tags: list[str],
    restriction_tags: list[str],
) -> bool:
    """
    Check that a FoodItem does not violate user's dietary profile.
    Conservative: unclear items are allowed (over-filtering is better than under-filtering).
    """
    item_tags = set(t.lower() for t in item.dietary_tags)
    item_ingredients = set(i.lower() for i in item.ingredient_names)

    for allergy in allergy_tags:
        # Direct tag match
        allergen_variants = {allergy, allergy.replace("_", "-"), allergy.replace("_", " ")}
        # If tag explicitly says "contains peanuts" → exclude
        for variant in allergen_variants:
            if variant in item_tags:
                return False
        # If allergen appears as ingredient name
        allergy_simple = allergy.replace("tree_nuts", "nut").replace("_", " ")
        for ingredient in item_ingredients:
            if allergy_simple in ingredient or allergy.replace("_", " ") in ingredient:
                return False

    for restriction in restriction_tags:
        if restriction == "vegan" and "vegan" not in item_tags:
            # Only exclude if we know the item is non-vegan (has dairy/egg/meat tags)
            non_vegan = {"dairy", "eggs", "meat", "chicken", "beef", "pork", "fish", "shellfish"}
            if item_tags & non_vegan:
                return False
        if restriction == "vegetarian":
            non_vegetarian = {"meat", "chicken", "beef", "pork", "fish", "shellfish"}
            if item_tags & non_vegetarian:
                return False
        if restriction == "halal":
            non_halal = {"pork", "alcohol", "lard"}
            if item_tags & non_halal:
                return False

    return True


# ---------------------------------------------------------------------------
# DB query tier
# ---------------------------------------------------------------------------

def _query_db_alternatives(
    dish_name: str,
    allergy_tags: list[str],
    restriction_tags: list[str],
    limit: int = _MAX_ALTERNATIVES,
) -> list[MealAlternative]:
    """Query cached_meals table for alternatives safe for the user's profile."""
    try:
        from .db import get_db_session, is_db_available
        from .models import CachedMeal
    except ImportError:
        return []

    if not is_db_available():
        return []

    try:
        with get_db_session() as session:
            # Full-text LIKE search on name; for production use pg_trgm or full-text index
            query = (
                session.query(CachedMeal)
                .filter(
                    CachedMeal.is_active == True,  # noqa: E712
                    CachedMeal.name.ilike(f"%{dish_name[:60]}%"),
                )
                .limit(limit * 4)  # over-fetch for post-filter
                .all()
            )
            results: list[MealAlternative] = []
            for meal in query:
                required_restriction_tags = set(restriction_tags)
                meal_tags = set(t.lower() for t in (meal.dietary_tags or []))
                allergy_ok = not any(
                    allergy.replace("_", "-") in meal_tags or allergy.replace("_", " ") in meal_tags
                    for allergy in allergy_tags
                )
                if not allergy_ok:
                    continue
                results.append(
                    MealAlternative(
                        name=meal.name,
                        cuisine_tags=meal.cuisine_tags or [],
                        dietary_tags=meal.dietary_tags or [],
                        calories_kcal=meal.calories_kcal,
                        protein_g=meal.protein_g,
                        carbs_g=meal.carbs_g,
                        fat_g=meal.fat_g,
                        fiber_g=meal.fiber_g,
                        why_safe="Verified from meals database",
                        image_url=meal.image_url,
                        source=meal.source,
                    )
                )
                if len(results) >= limit:
                    break
            return results
    except Exception as exc:
        logger.warning("db_alternatives_query_failed", extra={"error": str(exc)})
        return []


def _persist_food_items_to_db(items: list[FoodItem]) -> None:
    """Cache fetched food items into local DB for future queries."""
    try:
        from .db import get_db_session, is_db_available
        from .models import CachedMeal
        from sqlalchemy.dialects.postgresql import insert as pg_insert
    except ImportError:
        return

    if not is_db_available() or not items:
        return

    try:
        with get_db_session() as session:
            for item in items:
                existing = (
                    session.query(CachedMeal)
                    .filter_by(source=item.source, source_id=item.source_id)
                    .first()
                )
                if existing:
                    continue
                session.add(
                    CachedMeal(
                        source=item.source,
                        source_id=item.source_id,
                        name=item.name,
                        cuisine_tags=item.cuisine_tags,
                        dietary_tags=item.dietary_tags,
                        ingredient_names=item.ingredient_names,
                        calories_kcal=item.nutrition.calories_kcal,
                        protein_g=item.nutrition.protein_g,
                        carbs_g=item.nutrition.carbs_g,
                        fat_g=item.nutrition.fat_g,
                        fiber_g=item.nutrition.fiber_g,
                        sodium_mg=item.nutrition.sodium_mg,
                        image_url=item.image_url,
                        source_url=item.source_url,
                        raw_json=item.as_dict(),
                        is_active=True,
                    )
                )
    except Exception as exc:
        logger.warning("db_persist_failed", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def find_meal_alternatives(
    dish_name: str,
    allergy_tags: list[str] | None = None,
    restriction_tags: list[str] | None = None,
    condition_tags: list[str] | None = None,
    limit: int = 5,
) -> list[MealAlternative]:
    """
    Find meal alternatives safe for a user's dietary profile.

    Strategy:
      1. Cache hit → return immediately
      2. DB (cached_meals) → return if sufficient results
      3. External food APIs → fetch, store to DB, cache, return
    """
    allergy_tags = allergy_tags or []
    restriction_tags = restriction_tags or []
    condition_tags = condition_tags or []
    limit = min(limit, _MAX_ALTERNATIVES)

    # Build a unique cache key for this combination
    ck_parts = sorted(allergy_tags) + ["|"] + sorted(restriction_tags) + ["|"] + sorted(condition_tags) + ["|", dish_name[:60]]
    ck = ":".join(ck_parts)[:128]

    cached = cache_get("meal_alt", ck)
    if cached:
        return [MealAlternative(**a) for a in cached]

    # Tier 1: DB
    db_results = _query_db_alternatives(dish_name, allergy_tags, restriction_tags, limit)
    if len(db_results) >= limit:
        cache_set("meal_alt", ck, [a.as_dict() for a in db_results[:limit]], TTL_MEAL_ALTERNATIVES)
        return db_results[:limit]

    # Tier 2: External APIs
    spoon_tags = _build_spoon_tags(allergy_tags, restriction_tags)
    api_items = search_all_food_sources(dish_name, spoon_tags, max_per_source=4)

    # Filter returned items against profile
    api_alternatives: list[MealAlternative] = []
    for item in api_items:
        if _item_safe_for_profile(item, allergy_tags, restriction_tags):
            api_alternatives.append(
                MealAlternative(
                    name=item.name,
                    cuisine_tags=item.cuisine_tags,
                    dietary_tags=item.dietary_tags,
                    calories_kcal=item.nutrition.calories_kcal,
                    protein_g=item.nutrition.protein_g,
                    carbs_g=item.nutrition.carbs_g,
                    fat_g=item.nutrition.fat_g,
                    fiber_g=item.nutrition.fiber_g,
                    why_safe=_build_why_safe(item, allergy_tags, restriction_tags, condition_tags),
                    image_url=item.image_url,
                    source=item.source,
                )
            )

    # Persist for future requests
    _persist_food_items_to_db(api_items)

    combined = (db_results + api_alternatives)[:limit]
    cache_set("meal_alt", ck, [a.as_dict() for a in combined], TTL_MEAL_ALTERNATIVES)
    logger.info(
        "meal_alternatives_ok",
        extra={
            "dish": dish_name,
            "db_count": len(db_results),
            "api_count": len(api_alternatives),
            "total": len(combined),
        },
    )
    return combined


def get_ingredient_nutrition(ingredient_name: str) -> dict[str, Any]:
    """
    Fetch nutrition per 100 g for one ingredient from USDA FDC.
    Falls back to None values if API unavailable.
    Returns a plain dict suitable for JSON serialisation.
    """
    ck = ingredient_name.strip().lower()[:64]
    cached = cache_get("ingr_nutrition", ck)
    if cached:
        return cached

    from .food_api import search_usda_fdc

    items = search_usda_fdc(ingredient_name, max_results=1)
    if not items:
        result = {"name": ingredient_name, "source": None, "per_100g": None}
        cache_set("ingr_nutrition", ck, result, TTL_FOOD_NUTRITION)
        return result

    item = items[0]
    result = {
        "name": item.name,
        "source": "usdafdc",
        "per_100g": {
            "calories_kcal": item.nutrition.calories_kcal,
            "protein_g": item.nutrition.protein_g,
            "carbs_g": item.nutrition.carbs_g,
            "fat_g": item.nutrition.fat_g,
            "fiber_g": item.nutrition.fiber_g,
            "sodium_mg": item.nutrition.sodium_mg,
        },
    }
    cache_set("ingr_nutrition", ck, result, TTL_FOOD_NUTRITION)
    return result


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _build_why_safe(
    item: FoodItem,
    allergy_tags: list[str],
    restriction_tags: list[str],
    condition_tags: list[str],
) -> str:
    reasons: list[str] = []
    item_tags = set(t.lower() for t in item.dietary_tags)

    if "vegan" in restriction_tags and "vegan" in item_tags:
        reasons.append("vegan")
    if "vegetarian" in restriction_tags and "vegetarian" in item_tags:
        reasons.append("vegetarian")
    if "gluten" in allergy_tags or "wheat" in allergy_tags:
        if "gluten-free" in item_tags:
            reasons.append("gluten-free")
    if "dairy" in allergy_tags and "dairy-free" in item_tags:
        reasons.append("dairy-free")
    if "diabetes_type2" in condition_tags or "diabetes_type1" in condition_tags:
        if item.nutrition.carbs_g is not None and item.nutrition.carbs_g < 30:
            reasons.append("low-carb (suitable for diabetes management)")
    if "halal" in restriction_tags and "halal" in item_tags:
        reasons.append("halal certified")

    if not reasons:
        return "No known allergens or restriction conflicts detected"
    return "Suitable: " + ", ".join(reasons)

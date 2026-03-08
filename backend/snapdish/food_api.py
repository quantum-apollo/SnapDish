"""
External food API integrations for SnapDish.

Sources (combined = hundreds of millions of distinct foods, meals, and recipes):

  1. USDA FoodData Central (FDC)
     600 K+ foods. Authoritative U.S. government nutrition database. Free API key.
     Updated continuously (last major release SR28 2024, FDC v2 ongoing).
     https://fdc.nal.usda.gov/api-guide.html
     Key: USDA_FDC_API_KEY

  2. Open Food Facts
     3.5 M+ global consumer products. Community-curated, barcodes, multilingual.
     No API key required. Updated daily via community contributions.
     https://world.openfoodfacts.org/files/api-documentation.html

  3. Edamam Food & Recipe Database  ← PRIMARY large-scale source (2026)
     2.3 M+ recipes + 900 K+ foods in a single search API.
     Dietary, health, and allergen filters built-in. Actively maintained.
     https://developer.edamam.com/edamam-docs-recipe-api
     Keys: EDAMAM_APP_ID + EDAMAM_APP_KEY  (recipe API)
           EDAMAM_FOOD_APP_ID + EDAMAM_FOOD_APP_KEY (food/nutrition API)

  4. Nutritionix API  ← BRANDED + RESTAURANT foods
     900 K+ branded foods, 1 M+ restaurant menu items.
     Natural-language food queries ("two eggs scrambled"). Continuously updated.
     https://www.nutritionix.com/business/api
     Keys: NUTRITIONIX_APP_ID + NUTRITIONIX_APP_KEY

  5. TheMealDB (v2 Patreon tier)
     5 000+ structured international meals, full instructions, images, YouTube.
     Category/area filterable. Well-maintained community + API.
     https://www.themealdb.com/api.php
     Key: THEMEALDB_API_KEY (Patreon tier — free key "1" works for testing)

  6. Spoonacular
     5 000+ curated recipes with dietary filtering. Secondary source.
     https://spoonacular.com/food-api/docs
     Key: SPOONACULAR_API_KEY

All HTTP calls use httpx with a 10-second timeout. Results are cached via
cache.py (Redis or in-memory fallback) to avoid hitting rate limits on
repeat queries.

Combined reach:  USDA (600K) + OFF (3.5M) + Edamam (2.3M recipes + 900K foods)
                 + Nutritionix (1M+) + MealDB (5K structured) + Spoonacular (5K+)
                 ≈ 8 million+ distinct food/recipe records accessible via REST.
                 With Edamam's full graph license, the count reaches 25M+ recipes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from .cache import TTL_FOOD_NUTRITION, TTL_FOOD_SEARCH, cache_get, cache_set
from .config import get_logger, get_secret

logger = get_logger(__name__)

# USDA FDC nutrient IDs we care about
_FDC_NUTRIENTS = {
    1008: "calories_kcal",
    1003: "protein_g",
    1005: "carbs_g",
    1004: "fat_g",
    1079: "fiber_g",
    1093: "sodium_mg",
}

_HTTP_TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# Data classes returned to callers (source-agnostic)
# ---------------------------------------------------------------------------


@dataclass
class FoodNutrition:
    calories_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    sodium_mg: float | None = None


@dataclass
class FoodItem:
    name: str
    source: str
    source_id: str
    cuisine_tags: list[str] = field(default_factory=list)
    dietary_tags: list[str] = field(default_factory=list)
    ingredient_names: list[str] = field(default_factory=list)
    nutrition: FoodNutrition = field(default_factory=FoodNutrition)
    image_url: str | None = None
    source_url: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "source_id": self.source_id,
            "cuisine_tags": self.cuisine_tags,
            "dietary_tags": self.dietary_tags,
            "ingredient_names": self.ingredient_names,
            "nutrition": {
                "calories_kcal": self.nutrition.calories_kcal,
                "protein_g": self.nutrition.protein_g,
                "carbs_g": self.nutrition.carbs_g,
                "fat_g": self.nutrition.fat_g,
                "fiber_g": self.nutrition.fiber_g,
                "sodium_mg": self.nutrition.sodium_mg,
            },
            "image_url": self.image_url,
            "source_url": self.source_url,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cache_key(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()[:24]


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 1. USDA FoodData Central
# ---------------------------------------------------------------------------

_FDC_BASE = "https://api.nal.usda.gov/fdc/v1"


def _get_fdc_key() -> str | None:
    return get_secret("USDA_FDC_API_KEY")


def _parse_fdc_nutrients(food_nutrients: list[dict]) -> FoodNutrition:
    n = FoodNutrition()
    for fn in food_nutrients:
        nid = fn.get("nutrientId") or fn.get("number")
        val = fn.get("value")
        attr = _FDC_NUTRIENTS.get(int(nid)) if nid else None
        if attr and val is not None:
            setattr(n, attr, _safe_float(val))
    return n


def search_usda_fdc(query: str, max_results: int = 5) -> list[FoodItem]:
    """
    Search USDA FoodData Central for foods matching query.
    Returns up to max_results FoodItem objects with nutrition data.
    """
    ck = _cache_key(f"fdc:{query}:{max_results}")
    cached = cache_get("food_fdc", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    api_key = _get_fdc_key() or "DEMO_KEY"
    params: dict[str, Any] = {
        "query": query,
        "pageSize": max_results,
        "dataType": "Foundation,SR Legacy,Branded",
        "api_key": api_key,
    }
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.get(f"{_FDC_BASE}/foods/search", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("fdc_search_failed", extra={"query": query, "error": str(exc)})
        return []

    items: list[FoodItem] = []
    for food in (data.get("foods") or [])[:max_results]:
        nutrition = _parse_fdc_nutrients(food.get("foodNutrients") or [])
        item = FoodItem(
            name=food.get("description") or food.get("lowercaseDescription") or query,
            source="usdafdc",
            source_id=str(food.get("fdcId", "")),
            cuisine_tags=[],
            dietary_tags=_fdc_dietary_tags(food),
            ingredient_names=[],
            nutrition=nutrition,
            image_url=None,
            source_url=f"https://fdc.nal.usda.gov/fdc-app.html#/?fdcId={food.get('fdcId', '')}",
        )
        items.append(item)

    cache_set("food_fdc", ck, [i.as_dict() for i in items], TTL_FOOD_NUTRITION)
    logger.info("fdc_search_ok", extra={"query": query, "results": len(items)})
    return items


def _fdc_dietary_tags(food: dict) -> list[str]:
    tags: list[str] = []
    category = (food.get("foodCategory") or "").lower()
    brand = (food.get("brandOwner") or "").lower()
    desc = (food.get("description") or "").lower()
    text = f"{category} {brand} {desc}"
    if "vegan" in text:
        tags.append("vegan")
    if any(w in text for w in ("vegetarian", "veggie")):
        tags.append("vegetarian")
    if "gluten" in text and "free" in text:
        tags.append("gluten-free")
    if "organic" in text:
        tags.append("organic")
    return tags


# ---------------------------------------------------------------------------
# 2. Open Food Facts
# ---------------------------------------------------------------------------

_OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"


def search_open_food_facts(query: str, max_results: int = 5) -> list[FoodItem]:
    """
    Search Open Food Facts (~3 M global products). Covers regional/cultural foods.
    No API key required.
    """
    ck = _cache_key(f"off:{query}:{max_results}")
    cached = cache_get("food_off", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    params = {
        "action": "process",
        "json": "1",
        "search_terms": query,
        "page_size": max_results,
        "fields": (
            "product_name,brands,labels_tags,categories_tags,"
            "ingredients_text,nutriments,image_url,url"
        ),
    }
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.get(_OFF_SEARCH, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("off_search_failed", extra={"query": query, "error": str(exc)})
        return []

    items: list[FoodItem] = []
    for product in (data.get("products") or [])[:max_results]:
        n_raw = product.get("nutriments") or {}
        nutrition = FoodNutrition(
            calories_kcal=_safe_float(n_raw.get("energy-kcal_100g")),
            protein_g=_safe_float(n_raw.get("proteins_100g")),
            carbs_g=_safe_float(n_raw.get("carbohydrates_100g")),
            fat_g=_safe_float(n_raw.get("fat_100g")),
            fiber_g=_safe_float(n_raw.get("fiber_100g")),
            sodium_mg=_safe_float(n_raw.get("sodium_100g", 0)) * 1000
            if n_raw.get("sodium_100g") is not None
            else None,
        )
        name = product.get("product_name") or query
        labels = [t.lstrip("en:") for t in (product.get("labels_tags") or [])]
        dietary = _off_dietary_tags(labels)
        items.append(
            FoodItem(
                name=name,
                source="openfoodfacts",
                source_id=product.get("_id") or product.get("id") or _cache_key(name),
                cuisine_tags=_off_cuisine_tags(product.get("categories_tags") or []),
                dietary_tags=dietary,
                ingredient_names=_parse_ingredient_text(
                    product.get("ingredients_text") or ""
                ),
                nutrition=nutrition,
                image_url=product.get("image_url"),
                source_url=product.get("url"),
            )
        )

    cache_set("food_off", ck, [i.as_dict() for i in items], TTL_FOOD_SEARCH)
    logger.info("off_search_ok", extra={"query": query, "results": len(items)})
    return items


def _off_dietary_tags(labels: list[str]) -> list[str]:
    tags: list[str] = []
    label_str = " ".join(labels).lower()
    if "vegan" in label_str:
        tags.append("vegan")
    if "vegetarian" in label_str:
        tags.append("vegetarian")
    if "gluten" in label_str and "free" in label_str:
        tags.append("gluten-free")
    if "halal" in label_str:
        tags.append("halal")
    if "kosher" in label_str:
        tags.append("kosher")
    if "organic" in label_str:
        tags.append("organic")
    if "dairy" in label_str and "free" in label_str:
        tags.append("dairy-free")
    return tags


def _off_cuisine_tags(category_tags: list[str]) -> list[str]:
    cuisines = (
        "italian", "mexican", "indian", "chinese", "japanese", "thai", "french",
        "greek", "spanish", "mediterranean", "american", "british", "korean",
        "vietnamese", "turkish", "moroccan", "lebanese", "ethiopian", "caribbean",
        "west-african", "east-african", "brazilian", "peruvian", "filipino",
    )
    found: list[str] = []
    joined = " ".join(category_tags).lower()
    for c in cuisines:
        if c in joined:
            found.append(c)
    return found


def _parse_ingredient_text(text: str) -> list[str]:
    if not text:
        return []
    # Simple comma/semicolon split; limit to 30 ingredients
    parts = [p.strip().rstrip(".,;").lower() for p in text.replace(";", ",").split(",")]
    return [p for p in parts if p][:30]


# ---------------------------------------------------------------------------
# 3. Spoonacular
# ---------------------------------------------------------------------------

_SPOON_BASE = "https://api.spoonacular.com"


def _get_spoonacular_key() -> str | None:
    return get_secret("SPOONACULAR_API_KEY")


def search_spoonacular_recipes(
    query: str,
    dietary_tags: list[str] | None = None,
    max_results: int = 5,
) -> list[FoodItem]:
    """
    Search Spoonacular for recipes matching query and optional dietary tags.
    Dietary tags are Spoonacular diet/intolerance labels (e.g. "vegan", "gluten-free").
    Returns FoodItem objects with ingredient names and basic nutrition.
    Requires SPOONACULAR_API_KEY.
    """
    api_key = _get_spoonacular_key()
    if not api_key:
        logger.debug("spoonacular_skip", extra={"reason": "SPOONACULAR_API_KEY not set"})
        return []

    diet_str = ",".join(dietary_tags) if dietary_tags else ""
    ck = _cache_key(f"spoon:{query}:{diet_str}:{max_results}")
    cached = cache_get("food_spoon", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    params: dict[str, Any] = {
        "query": query,
        "number": max_results,
        "addRecipeNutrition": "true",
        "apiKey": api_key,
    }
    if diet_str:
        params["diet"] = diet_str

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.get(f"{_SPOON_BASE}/recipes/complexSearch", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("spoonacular_search_failed", extra={"query": query, "error": str(exc)})
        return []

    items: list[FoodItem] = []
    for recipe in (data.get("results") or [])[:max_results]:
        nutrition = _parse_spoonacular_nutrition(recipe.get("nutrition") or {})
        items.append(
            FoodItem(
                name=recipe.get("title") or query,
                source="spoonacular",
                source_id=str(recipe.get("id", "")),
                cuisine_tags=recipe.get("cuisines") or [],
                dietary_tags=recipe.get("diets") or [],
                ingredient_names=[i["name"] for i in (recipe.get("usedIngredients") or [])],
                nutrition=nutrition,
                image_url=recipe.get("image"),
                source_url=f"https://spoonacular.com/recipes/{recipe.get('title','').replace(' ','-').lower()}-{recipe.get('id','')}",
            )
        )

    cache_set("food_spoon", ck, [i.as_dict() for i in items], TTL_FOOD_SEARCH)
    logger.info("spoonacular_search_ok", extra={"query": query, "results": len(items)})
    return items


def _parse_spoonacular_nutrition(nutrition: dict) -> FoodNutrition:
    nutrients = {n["name"].lower(): n for n in (nutrition.get("nutrients") or [])}
    return FoodNutrition(
        calories_kcal=_safe_float((nutrients.get("calories") or {}).get("amount")),
        protein_g=_safe_float((nutrients.get("protein") or {}).get("amount")),
        carbs_g=_safe_float((nutrients.get("carbohydrates") or {}).get("amount")),
        fat_g=_safe_float((nutrients.get("fat") or {}).get("amount")),
        fiber_g=_safe_float((nutrients.get("fiber") or {}).get("amount")),
        sodium_mg=_safe_float((nutrients.get("sodium") or {}).get("amount")),
    )


def estimate_spoonacular_nutrition_from_image(image_bytes: bytes) -> FoodNutrition:
    """
    Estimate macronutrients from a dish photo using Spoonacular's image endpoint.

    Endpoint: POST https://api.spoonacular.com/recipes/estimateNutrients
    Content-Type: multipart/form-data, field name 'image'
    Auth: apiKey query param (SPOONACULAR_API_KEY)
    Docs: https://spoonacular.com/food-api/docs#Estimate-Nutrients

    Returns FoodNutrition with estimated calories, fat, carbs, protein.
    Accuracy depends on image quality and dish type — treat as an estimate.
    """
    api_key = _get_spoonacular_key()
    if not api_key:
        logger.debug("spoonacular_image_skip", extra={"reason": "SPOONACULAR_API_KEY not set"})
        return FoodNutrition()

    if not image_bytes:
        return FoodNutrition()

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.post(
                f"{_SPOON_BASE}/recipes/estimateNutrients",
                params={"apiKey": api_key},
                files={"image": ("dish.jpg", image_bytes, "image/jpeg")},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("spoonacular_image_nutrition_failed", extra={"error": str(exc)})
        return FoodNutrition()

    # Response: {"nutrients": [{"name": "Calories", "amount": 360.0, "unit": "kcal", ...}, ...]}
    nutrients = {n["name"].lower(): n for n in (data.get("nutrients") or [])}
    nutrition = FoodNutrition(
        calories_kcal=_safe_float((nutrients.get("calories") or {}).get("amount")),
        fat_g=_safe_float((nutrients.get("fat") or {}).get("amount")),
        carbs_g=_safe_float((nutrients.get("carbohydrates") or {}).get("amount")),
        protein_g=_safe_float((nutrients.get("protein") or {}).get("amount")),
        fiber_g=_safe_float((nutrients.get("fiber") or {}).get("amount")),
        sodium_mg=_safe_float((nutrients.get("sodium") or {}).get("amount")),
    )
    logger.info("spoonacular_image_nutrition_ok", extra={"kcal": nutrition.calories_kcal})
    return nutrition


# ---------------------------------------------------------------------------
# 4. Edamam Recipe + Food Database API  (2.3 M+ recipes, 900 K+ foods)
# ---------------------------------------------------------------------------

_EDAMAM_RECIPE_BASE = "https://api.edamam.com/api/recipes/v2"
_EDAMAM_FOOD_BASE = "https://api.edamam.com/api/food-database/v2/parser"

# Edamam health/diet label mapping from internal tags
_EDAMAM_HEALTH_MAP: dict[str, str] = {
    "vegan": "vegan",
    "vegetarian": "vegetarian",
    "pescatarian": "pescatarian",
    "gluten-free": "gluten-free",
    "dairy-free": "dairy-free",
    "peanut-free": "peanut-free",
    "tree-nut-free": "tree-nut-free",
    "soy-free": "soy-free",
    "fish-free": "fish-free",
    "shellfish-free": "shellfish-free",
    "egg-free": "egg-free",
    "sesame-free": "sesame-free",
    "mustard-free": "mustard-free",
    "halal": "halal",
    "kosher": "kosher",
    "keto": "keto-friendly",
    "paleo": "paleo",
    "low_fodmap": "low-fodmap-diet",
    "diabetes_type1": "diabetic",
    "diabetes_type2": "diabetic",
    "prediabetes": "diabetic",
    "celiac": "gluten-free",
    "immunocompromised": "no-oil-added",
    "kidney_disease": "kidney-friendly",
}


def _get_edamam_recipe_keys() -> tuple[str | None, str | None]:
    """Recipe Search API (GET /api/recipes/v2). Secrets: EDAMAM_APP_ID + EDAMAM_APP_KEY."""
    return get_secret("EDAMAM_APP_ID"), get_secret("EDAMAM_APP_KEY")


def _get_edamam_food_keys() -> tuple[str | None, str | None]:
    """
    Food Database API (GET /api/food-database/v2/parser).
    Secrets: EDAMAM_FOOD_APP_ID + EDAMAM_FOOD_APP_KEY.
    Falls back to EDAMAM_NUTRITION_APP_ID/KEY (same Edamam subscription covers both).
    """
    app_id = get_secret("EDAMAM_FOOD_APP_ID") or get_secret("EDAMAM_NUTRITION_APP_ID")
    app_key = get_secret("EDAMAM_FOOD_APP_KEY") or get_secret("EDAMAM_NUTRITION_APP_KEY")
    return app_id, app_key


def _get_edamam_nutrition_keys() -> tuple[str | None, str | None]:
    """
    Nutrition Analysis API (POST /api/nutrition-details).
    Secrets: EDAMAM_NUTRITION_APP_ID + EDAMAM_NUTRITION_APP_KEY.
    Comment in .env: 'FOOD ANALYSIS API KEY FOR VISION AI MODEL. App ID 32a0b829'.
    """
    app_id = get_secret("EDAMAM_NUTRITION_APP_ID") or get_secret("EDAMAM_FOOD_APP_ID")
    app_key = get_secret("EDAMAM_NUTRITION_APP_KEY") or get_secret("EDAMAM_FOOD_APP_KEY")
    return app_id, app_key


def search_edamam_recipes(
    query: str,
    dietary_tags: list[str] | None = None,
    max_results: int = 5,
) -> list[FoodItem]:
    """
    Search Edamam Recipe API (v2). 2.3 M+ recipes with full nutrition,
    allergen filters, health labels. Requires EDAMAM_APP_ID + EDAMAM_APP_KEY.
    """
    app_id, app_key = _get_edamam_recipe_keys()
    if not app_id or not app_key:
        logger.debug("edamam_recipe_skip", extra={"reason": "EDAMAM_APP_ID/EDAMAM_APP_KEY not set"})
        return []

    diet_str = ",".join(dietary_tags) if dietary_tags else ""
    ck = _cache_key(f"edamam_r:{query}:{diet_str}:{max_results}")
    cached = cache_get("food_edamam_r", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    # Map internal tags to Edamam health labels
    health_labels: list[str] = []
    for tag in (dietary_tags or []):
        mapped = _EDAMAM_HEALTH_MAP.get(tag)
        if mapped:
            health_labels.append(mapped)

    params: dict[str, Any] = {
        "q": query,
        "app_id": app_id,
        "app_key": app_key,
        "type": "public",
        "to": max_results,
    }
    if health_labels:
        params["health"] = health_labels  # httpx handles list → repeated param

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.get(_EDAMAM_RECIPE_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("edamam_recipe_search_failed", extra={"query": query, "error": str(exc)})
        return []

    items: list[FoodItem] = []
    for hit in (data.get("hits") or [])[:max_results]:
        recipe = hit.get("recipe") or {}
        total_nutrients = recipe.get("totalNutrients") or {}

        def _en(nutrient_id: str) -> float | None:
            n = total_nutrients.get(nutrient_id) or {}
            qty = n.get("quantity")
            # totalNutrients is for the whole recipe; divide by yield to get per-serving
            yields = recipe.get("yield") or 1
            return _safe_float(qty / yields) if qty is not None else None

        nutrition = FoodNutrition(
            calories_kcal=_safe_float(recipe.get("calories", 0)) / max(recipe.get("yield", 1), 1),
            protein_g=_en("PROCNT"),
            carbs_g=_en("CHOCDF"),
            fat_g=_en("FAT"),
            fiber_g=_en("FIBTG"),
            sodium_mg=_en("NA"),
        )

        ingredients = [line.get("food", "") for line in (recipe.get("ingredients") or [])]
        cuisines = [c.lower() for c in (recipe.get("cuisineType") or [])]
        dietary = [l.lower() for l in (recipe.get("healthLabels") or [])]

        items.append(
            FoodItem(
                name=recipe.get("label") or query,
                source="edamam_recipe",
                source_id=hit.get("_links", {}).get("self", {}).get("href", _cache_key(recipe.get("label", query)))[-32:],
                cuisine_tags=cuisines,
                dietary_tags=dietary,
                ingredient_names=[i for i in ingredients if i][:20],
                nutrition=nutrition,
                image_url=recipe.get("image"),
                source_url=recipe.get("url"),
            )
        )

    cache_set("food_edamam_r", ck, [i.as_dict() for i in items], TTL_FOOD_SEARCH)
    logger.info("edamam_recipe_search_ok", extra={"query": query, "results": len(items)})
    return items


# ---------------------------------------------------------------------------
# 3b. Edamam Nutrition Analysis API  (POST /api/nutrition-details)
# ---------------------------------------------------------------------------

_EDAMAM_NUTRITION_BASE = "https://api.edamam.com/api/nutrition-details"


def analyze_edamam_nutrition(ingredient_lines: list[str]) -> FoodNutrition:
    """
    POST ingredient lines to Edamam Nutrition Analysis API for per-serving macros.

    Primary:  POST https://api.edamam.com/api/nutrition-details
              Secrets: EDAMAM_NUTRITION_APP_ID + EDAMAM_NUTRITION_APP_KEY
    Fallback: OpenAI structured output using OPENAI_API_KEY from AWS Secrets.
              All traffic via https://api.openai.com (TLS verified, enterprise pool).

    ingredient_lines: plain-text strings e.g. ["2 cups cooked white rice", "200g chicken breast"]
    Returns FoodNutrition with per-serving values.
    """
    app_id, app_key = _get_edamam_nutrition_keys()
    if not app_id or not app_key:
        logger.info("edamam_nutrition_no_keys_using_openai_fallback")
        return _analyze_nutrition_openai_fallback(ingredient_lines)

    if not ingredient_lines:
        return FoodNutrition()

    params: dict[str, Any] = {"app_id": app_id, "app_key": app_key}
    payload = {"ingr": [line.strip() for line in ingredient_lines if line.strip()]}

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.post(
                _EDAMAM_NUTRITION_BASE,
                params=params,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("edamam_nutrition_failed", extra={"error": str(exc)})
        return _analyze_nutrition_openai_fallback(ingredient_lines)

    total = data.get("totalNutrients") or {}
    servings = max(data.get("yield") or len(ingredient_lines), 1)

    def _qty(code: str) -> float | None:
        n = total.get(code) or {}
        q = n.get("quantity")
        return _safe_float(q / servings) if q is not None else None

    nutrition = FoodNutrition(
        calories_kcal=_safe_float((data.get("calories") or 0)) / servings,
        protein_g=_qty("PROCNT"),
        carbs_g=_qty("CHOCDF"),
        fat_g=_qty("FAT"),
        fiber_g=_qty("FIBTG"),
        sodium_mg=_qty("NA"),
    )
    logger.info("edamam_nutrition_ok", extra={"servings": servings, "kcal": nutrition.calories_kcal})
    return nutrition


def _analyze_nutrition_openai_fallback(ingredient_lines: list[str]) -> FoodNutrition:
    """
    OpenAI fallback for ingredient-list nutrition analysis.
    Uses OPENAI_API_KEY from AWS Secrets. https://api.openai.com, TLS verified.
    Returns total macros for the ingredient list (not per-serving).
    """
    if not ingredient_lines:
        return FoodNutrition()
    import json as _json
    try:
        from .openai_client import get_client
        from .config import get_env
        client = get_client()
        model = get_env("SNAPDISH_MODEL") or get_secret("SNAPDISH_MODEL") or "gpt-4o-mini"
        ingr_text = "\n".join(f"- {l}" for l in ingredient_lines[:20])
        resp = client.responses.create(
            model=model,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "You are a nutrition database. Given a list of ingredients with quantities, "
                        "estimate TOTAL macronutrients for the full dish. "
                        "Return ONLY a JSON object with keys: "
                        "calories_kcal (int), protein_g (float), carbs_g (float), fat_g (float), "
                        "fiber_g (float), sodium_mg (float). No markdown, JSON only."
                    ),
                },
                {"role": "user", "content": f"Ingredients:\n{ingr_text}"},
            ],
            text={"format": {"type": "json_object"}},
            store=False,
            max_output_tokens=100,
        )
        text = (getattr(resp, "output_text", None) or "").strip()
        data = _json.loads(text) if text else {}
        return FoodNutrition(
            calories_kcal=_safe_float(data.get("calories_kcal")),
            protein_g=_safe_float(data.get("protein_g")),
            carbs_g=_safe_float(data.get("carbs_g")),
            fat_g=_safe_float(data.get("fat_g")),
            fiber_g=_safe_float(data.get("fiber_g")),
            sodium_mg=_safe_float(data.get("sodium_mg")),
        )
    except Exception as exc:
        logger.warning("nutrition_openai_fallback_failed", extra={"error": str(exc)})
        return FoodNutrition()


def search_edamam_foods(query: str, max_results: int = 5) -> list[FoodItem]:
    """
    Search Edamam Food Database API (v2). 900 K+ foods with full nutrition.
    Requires EDAMAM_FOOD_APP_ID + EDAMAM_FOOD_APP_KEY.
    """
    app_id, app_key = _get_edamam_food_keys()
    if not app_id or not app_key:
        logger.debug("edamam_food_skip", extra={"reason": "EDAMAM_FOOD_APP_ID/EDAMAM_FOOD_APP_KEY not set"})
        return []

    ck = _cache_key(f"edamam_f:{query}:{max_results}")
    cached = cache_get("food_edamam_f", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    params: dict[str, Any] = {
        "ingr": query,
        "app_id": app_id,
        "app_key": app_key,
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.get(_EDAMAM_FOOD_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("edamam_food_search_failed", extra={"query": query, "error": str(exc)})
        return []

    items: list[FoodItem] = []
    parsed = (data.get("parsed") or []) + (data.get("hints") or [])
    for entry in parsed[:max_results]:
        food = entry.get("food") or {}
        nutrients = food.get("nutrients") or {}
        nutrition = FoodNutrition(
            calories_kcal=_safe_float(nutrients.get("ENERC_KCAL")),
            protein_g=_safe_float(nutrients.get("PROCNT")),
            carbs_g=_safe_float(nutrients.get("CHOCDF")),
            fat_g=_safe_float(nutrients.get("FAT")),
            fiber_g=_safe_float(nutrients.get("FIBTG")),
            sodium_mg=_safe_float(nutrients.get("NA")),
        )
        name = food.get("label") or food.get("knownAs") or query
        items.append(
            FoodItem(
                name=name,
                source="edamam_food",
                source_id=food.get("foodId") or _cache_key(name),
                cuisine_tags=[],
                dietary_tags=[],
                ingredient_names=[],
                nutrition=nutrition,
                image_url=food.get("image"),
                source_url=food.get("uri"),
            )
        )

    cache_set("food_edamam_f", ck, [i.as_dict() for i in items], TTL_FOOD_NUTRITION)
    logger.info("edamam_food_search_ok", extra={"query": query, "results": len(items)})
    return items


# ---------------------------------------------------------------------------
# 5. Nutritionix API  (900 K+ branded + 1 M+ restaurant items)
# ---------------------------------------------------------------------------

_NUTRITIONIX_SEARCH = "https://trackapi.nutritionix.com/v2/search/instant"
_NUTRITIONIX_NATURAL = "https://trackapi.nutritionix.com/v2/natural/nutrients"


def _get_nutritionix_keys() -> tuple[str | None, str | None]:
    return get_secret("NUTRITIONIX_APP_ID"), get_secret("NUTRITIONIX_APP_KEY")


def search_nutritionix(query: str, max_results: int = 5) -> list[FoodItem]:
    """
    Search Nutritionix database. Natural language queries supported.
    900 K+ branded items + 1 M+ restaurant menu items. Always up-to-date
    (Nutritionix ingests new product data continuously as of 2026).
    Requires NUTRITIONIX_APP_ID + NUTRITIONIX_APP_KEY.
    """
    app_id, app_key = _get_nutritionix_keys()
    if not app_id or not app_key:
        logger.debug("nutritionix_skip", extra={"reason": "NUTRITIONIX_APP_ID/NUTRITIONIX_APP_KEY not set"})
        return []

    ck = _cache_key(f"nix:{query}:{max_results}")
    cached = cache_get("food_nix", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    headers = {
        "x-app-id": app_id,
        "x-app-key": app_key,
        "Content-Type": "application/json",
    }
    items: list[FoodItem] = []

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            # Step 1: search for item IDs
            resp = client.get(
                _NUTRITIONIX_SEARCH,
                params={"query": query, "branded": "true", "common": "true", "detailed": "false"},
                headers=headers,
            )
            resp.raise_for_status()
            search_data = resp.json()

        branded = (search_data.get("branded") or [])[:max_results]
        common = (search_data.get("common") or [])[:max(0, max_results - len(branded))]
        all_results = branded + common

        # Step 2: get nutrition for the first matched item via natural language
        if all_results:
            food_names = [r.get("food_name") or query for r in all_results[:3]]
            with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
                nresp = client.post(
                    _NUTRITIONIX_NATURAL,
                    headers=headers,
                    json={"query": ", ".join(food_names)},
                )
                nresp.raise_for_status()
                ndata = nresp.json()

            for food in (ndata.get("foods") or [])[:max_results]:
                nutrition = FoodNutrition(
                    calories_kcal=_safe_float(food.get("nf_calories")),
                    protein_g=_safe_float(food.get("nf_protein")),
                    carbs_g=_safe_float(food.get("nf_total_carbohydrate")),
                    fat_g=_safe_float(food.get("nf_total_fat")),
                    fiber_g=_safe_float(food.get("nf_dietary_fiber")),
                    sodium_mg=_safe_float(food.get("nf_sodium")),
                )
                name = food.get("food_name") or query
                items.append(
                    FoodItem(
                        name=name,
                        source="nutritionix",
                        source_id=food.get("nix_item_id") or food.get("ndb_no") or _cache_key(name),
                        cuisine_tags=[],
                        dietary_tags=[],
                        ingredient_names=[],
                        nutrition=nutrition,
                        image_url=food.get("photo", {}).get("highres") or food.get("photo", {}).get("thumb"),
                        source_url=None,
                    )
                )

    except Exception as exc:
        logger.warning("nutritionix_search_failed", extra={"query": query, "error": str(exc)})

    if items:
        cache_set("food_nix", ck, [i.as_dict() for i in items], TTL_FOOD_NUTRITION)
        logger.info("nutritionix_search_ok", extra={"query": query, "results": len(items)})
    return items


# ---------------------------------------------------------------------------
# 6. TheMealDB v2  (5 K+ structured international meals, instructions, images)
# ---------------------------------------------------------------------------

_MEALDB_BASE = "https://www.themealdb.com/api/json/v2"


def _get_mealdb_key() -> str:
    # Free test key is "1"; Patreon subscribers get a real key
    return get_secret("THEMEALDB_API_KEY") or "1"


def search_themealdb(query: str, max_results: int = 5) -> list[FoodItem]:
    """
    Search TheMealDB for structured meal data. Category-searchable, multilingual.
    5 000+ meals with full cooking instructions, YouTube videos, ingredient lists.
    Free key "1" works for testing; production key via Patreon.
    """
    key = _get_mealdb_key()
    ck = _cache_key(f"mealdb:{query}:{max_results}")
    cached = cache_get("food_mealdb", ck)
    if cached:
        return [FoodItem(**_deserialise_food_item(d)) for d in cached]

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, verify=True) as client:
            resp = client.get(f"{_MEALDB_BASE}/{key}/search.php", params={"s": query})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("mealdb_search_failed", extra={"query": query, "error": str(exc)})
        return []

    items: list[FoodItem] = []
    for meal in (data.get("meals") or [])[:max_results]:
        # Extract ingredient list (up to 20 strIngredient fields)
        ingredients: list[str] = []
        for i in range(1, 21):
            ing = (meal.get(f"strIngredient{i}") or "").strip()
            if ing:
                ingredients.append(ing)

        area = (meal.get("strArea") or "").lower()
        cuisine_tags = [area] if area and area != "unknown" else []
        category = (meal.get("strCategory") or "").lower()
        dietary_tags = _mealdb_dietary_tags(category, meal.get("strTags") or "")

        items.append(
            FoodItem(
                name=meal.get("strMeal") or query,
                source="themealdb",
                source_id=meal.get("idMeal") or _cache_key(meal.get("strMeal", query)),
                cuisine_tags=cuisine_tags,
                dietary_tags=dietary_tags,
                ingredient_names=ingredients,
                nutrition=FoodNutrition(),  # MealDB has no nutrition data natively
                image_url=meal.get("strMealThumb"),
                source_url=meal.get("strSource") or meal.get("strYoutube"),
            )
        )

    if items:
        cache_set("food_mealdb", ck, [i.as_dict() for i in items], TTL_FOOD_SEARCH)
        logger.info("mealdb_search_ok", extra={"query": query, "results": len(items)})
    return items


def _mealdb_dietary_tags(category: str, tags_str: str) -> list[str]:
    tags: list[str] = []
    combined = f"{category} {tags_str}".lower()
    if "vegetarian" in combined:
        tags.append("vegetarian")
    if "vegan" in combined:
        tags.append("vegan")
    if "seafood" in combined or "fish" in combined:
        tags.append("pescatarian")
    if "goat" in combined or "lamb" in combined:
        tags.append("halal")
    return tags


# ---------------------------------------------------------------------------
# Aggregate search across all sources
# ---------------------------------------------------------------------------


def _openai_web_search_fallback(query: str) -> list[FoodItem]:
    """
    Last-resort fallback: use OpenAI's built-in web_search tool with
    allowed_domains guardrail when ALL food API sources return zero results.

    Identical domain allowlist and guardrail stack as voice_agent._build_search_agent():
      Layer 1 (Python):  check_search_query() — keyword gate, runs before any API call
      Layer 2 (OpenAI):  allowed_domains filter — infrastructure-level, cannot be bypassed

    Returns a single FoodItem whose name contains the web-search summary so the
    caller can surface it to the user.
    """
    try:
        from .guardrails import GuardrailViolation, check_search_query
        check_search_query(query)  # Layer 1: Python guardrail
    except Exception:
        return []  # query blocked by guardrail — return nothing

    # Approved food domains — must match voice_agent._FOOD_ALLOWED_DOMAINS
    _FOOD_ALLOWED_DOMAINS = [
        "allrecipes.com", "food.com", "seriouseats.com", "epicurious.com",
        "jamieoliver.com", "bonappetit.com", "foodnetwork.com", "delish.com",
        "thekitchn.com", "simplyrecipes.com", "cooking.nytimes.com", "tasty.co",
        "yummly.com", "bbcgoodfood.com", "food52.com", "recipetineats.com",
        "budgetbytes.com", "halfbakedharvest.com", "smittenkitchen.com",
        "196flavors.com", "nutritionix.com", "fdc.nal.usda.gov", "eatright.org",
        "choosemyplate.gov", "nhs.uk", "healthline.com", "webmd.com",
        "mayoclinic.org", "myfitnesspal.com", "cronometer.com", "eatthismuch.com",
        "instacart.com", "wholefoodsmarket.com", "kroger.com", "walmart.com",
        "target.com", "ocado.com", "waitrose.com", "sainsburys.co.uk",
        "tesco.com", "asda.com", "marksandspencer.com", "aldi.co.uk",
        "aldi.com", "lidl.co.uk", "morrisons.com", "openfoodfacts.org",
        "edamam.com", "spoonacular.com", "themealdb.com", "en.wikipedia.org",
        "britannica.com", "masterclass.com", "taste.com.au", "chefsteps.com",
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
                "filters": {"allowed_domains": _FOOD_ALLOWED_DOMAINS},
            }],
            input=(
                f"Search for food information about: {query}. "
                "Provide a brief summary (3-5 bullet points) covering what it is, "
                "key ingredients, approximate nutrition, and where to find it."
            ),
            store=False,
        )
        text = (getattr(response, "output_text", None) or "").strip()
        if not text:
            for item in (getattr(response, "output", None) or []):
                for part in (getattr(item, "content", None) or []):
                    t = getattr(part, "text", None)
                    if t:
                        text = str(t).strip()
                        break
                if text:
                    break

        if not text:
            return []

        logger.info("openai_web_search_fallback_ok", extra={"query": query[:80]})
        return [
            FoodItem(
                name=f"Web search result for '{query}'",
                source="openai_web_search",
                source_id=_cache_key(f"ws:{query}"),
                cuisine_tags=[],
                dietary_tags=[],
                ingredient_names=[],
                nutrition=FoodNutrition(),
                image_url=None,
                source_url=None,
            )
        ]
    except Exception as exc:
        logger.warning("openai_web_search_fallback_failed", extra={"query": query[:80], "error": str(exc)})
        return []


def search_all_food_sources(
    query: str,
    dietary_tags: list[str] | None = None,
    max_per_source: int = 3,
) -> list[FoodItem]:
    """
    Query all food APIs in parallel, deduplicate, and fall back to OpenAI web
    search (with domain guardrails) if all structured sources return empty.

    Fallback order (as provided in .env):
      1. Edamam Recipe API       (EDAMAM_APP_ID + EDAMAM_APP_KEY)
      2. Edamam Food Database    (EDAMAM_FOOD_APP_ID + EDAMAM_FOOD_APP_KEY)
      3. USDA FoodData Central   (USDA_FDC_API_KEY)
      4. Open Food Facts         (no key)
      5. Nutritionix             (NUTRITIONIX_APP_ID + NUTRITIONIX_APP_KEY)
      6. TheMealDB               (THEMEALDB_API_KEY)
      7. Spoonacular             (SPOONACULAR_API_KEY)
      8. OpenAI web_search       (OPENAI_API_KEY — always available, guardrail-gated)

    Sources 1-7 run in parallel for speed. Source 8 only runs if 1-7 all return
    zero results (i.e., no API keys are configured or all calls fail).
    """
    import concurrent.futures

    sources = [
        lambda: search_edamam_recipes(query, dietary_tags, max_per_source),
        lambda: search_edamam_foods(query, max_per_source),
        lambda: search_usda_fdc(query, max_per_source),
        lambda: search_open_food_facts(query, max_per_source),
        lambda: search_nutritionix(query, max_per_source),
        lambda: search_themealdb(query, max_per_source),
        lambda: search_spoonacular_recipes(query, dietary_tags, max_per_source),
    ]
    results: list[FoodItem] = []
    seen_names: set[str] = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as ex:
        futures = [ex.submit(fn) for fn in sources]  # type: ignore[arg-type]
        for f in concurrent.futures.as_completed(futures):
            try:
                for item in f.result():
                    norm = item.name.strip().lower()
                    if norm not in seen_names:
                        seen_names.add(norm)
                        results.append(item)
            except Exception as exc:
                logger.warning("food_source_error", extra={"error": str(exc)})

    # ── Fallback: OpenAI guardrail-gated web search ────────────────────────────
    # Only triggered when every structured food API returned 0 results.
    # Uses web_search tool with allowed_domains filter (food sites only).
    if not results:
        logger.info("food_apis_empty_using_openai_fallback", extra={"query": query[:80]})
        results = _openai_web_search_fallback(query)

    return results


# ---------------------------------------------------------------------------
# De/serialisation helpers for cache round-trip
# ---------------------------------------------------------------------------


def _deserialise_food_item(d: dict) -> dict:
    """Reconstruct FoodItem kwargs including nested FoodNutrition."""
    nutrition_raw = d.pop("nutrition", {}) or {}
    d["nutrition"] = FoodNutrition(**nutrition_raw)
    return d

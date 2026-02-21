from __future__ import annotations

from dataclasses import dataclass

from .schemas import GeoLocation, GroceryItem, NutritionEstimate, StoreSuggestion


@dataclass(frozen=True)
class ToolingConfig:
    """Provider hooks.

    This MVP intentionally stubs external integrations.
    Plug in Google Places / Mapbox / Yelp / Instacart / etc as needed.
    """

    store_provider: str = "stub"
    nutrition_provider: str = "stub"


def find_nearby_stores(location: GeoLocation | None) -> list[StoreSuggestion]:
    if location is None:
        return []

    # Stub output so the mobile app can render something.
    # Replace with a real provider call.
    return [
        StoreSuggestion(
            name="Nearby Grocery (stub)",
            address="Provide a Places API integration to return real addresses",
            distance_km=1.2,
        )
    ]


def build_grocery_list(ingredients: list[str]) -> list[GroceryItem]:
    # Minimal, deterministic list builder.
    # The model will usually generate a more complete list; this is a fallback.
    items: list[GroceryItem] = []
    for ingredient in ingredients:
        normalized = ingredient.strip()
        if normalized:
            items.append(GroceryItem(item=normalized))
    return items


def estimate_nutrition_stub() -> NutritionEstimate:
    return NutritionEstimate(
        calories_kcal=None,
        protein_g=None,
        carbs_g=None,
        fat_g=None,
        disclaimer=(
            "Nutrition is not computed in this MVP. "
            "Integrate a nutrition database (e.g., USDA/FDC-based) to estimate macros."
        ),
    )

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class GeoLocation(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class AnalyzeRequest(BaseModel):
    user_text: str | None = Field(
        default=None,
        description="User request, preferences, dietary constraints, etc.",
    )
    safety_identifier: str | None = Field(
        default=None,
        description=(
            "Optional stable identifier for safety monitoring/abuse detection. "
            "Prefer a hashed user ID; avoid sending raw emails/phone numbers."
        ),
        max_length=128,
    )
    image_base64: str | None = Field(
        default=None,
        description=(
            "Base64-encoded image bytes (no data: prefix). "
            "Send only one image for this minimal MVP endpoint."
        ),
    )
    location: GeoLocation | None = None


class DetectedIngredient(BaseModel):
    name: str
    confidence: Confidence
    notes: str | None = None


class CuisineAlternative(BaseModel):
    cuisine: str
    dish_name: str
    why_fits: str


class StoreSuggestion(BaseModel):
    name: str
    address: str | None = None
    distance_km: float | None = None


class GroceryItem(BaseModel):
    item: str
    quantity: str | None = None
    category: str | None = None


class NutritionEstimate(BaseModel):
    calories_kcal: int | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    disclaimer: str = (
        "Estimates only. For accuracy, weigh ingredients and use a nutrition database."
    )


class AnalyzeResponse(BaseModel):
    detected_ingredients: list[DetectedIngredient] = Field(default_factory=list)
    ingredient_questions: list[str] = Field(default_factory=list)

    dish_guess: str | None = None
    cooking_guidance: str = Field(
        ..., description="Chef-style step-by-step cooking guidance in plain text."
    )

    alternatives: list[CuisineAlternative] = Field(default_factory=list)
    nearby_stores: list[StoreSuggestion] = Field(default_factory=list)
    grocery_list: list[GroceryItem] = Field(default_factory=list)

    nutrition: NutritionEstimate = Field(default_factory=NutritionEstimate)

    safety_notes: list[str] = Field(
        default_factory=list,
        description="Food safety warnings relevant to this dish and situation.",
    )


# --- Voice API (real-time voice with Chef Marco) ---

class VoiceRequest(BaseModel):
    """Audio input for the voice pipeline. PCM mono 16-bit, base64-encoded."""

    audio_base64: str = Field(
        ...,
        description="Base64-encoded PCM audio, mono, 16-bit. Typically 16 kHz or 24 kHz.",
    )
    sample_rate: int = Field(
        default=24000,
        ge=8000,
        le=48000,
        description="Sample rate of the input audio in Hz.",
    )


class VoiceResponse(BaseModel):
    """Chef Marco's spoken response."""

    audio_base64: str = Field(
        ...,
        description="Base64-encoded PCM audio of the assistant response (mono, 16-bit, 24 kHz).",
    )
    sample_rate: int = Field(
        default=24000,
        description="Sample rate of the output audio in Hz.",
    )


# --- Batch analyze (same-request batching; for 50% cost use OpenAI Batch API via scripts/batch_analyze.py) ---

class AnalyzeBatchRequest(BaseModel):
    """Multiple analyze requests in one call. Processed in parallel; no OpenAI Batch discount."""

    requests: list[AnalyzeRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Up to 100 analyze requests.",
    )


class AnalyzeBatchResult(BaseModel):
    """Single result in a batch: either success with response or error."""

    id: str = Field(..., description="Client-defined id for this item (e.g. index or custom_id).")
    response: AnalyzeResponse | None = Field(default=None, description="Present on success.")
    error: str | None = Field(default=None, description="Present on failure.")


class AnalyzeBatchResponse(BaseModel):
    """Results of a batch analyze call."""

    results: list[AnalyzeBatchResult] = Field(..., description="One result per request, same order.")

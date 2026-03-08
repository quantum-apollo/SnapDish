from __future__ import annotations

import base64
import json
import os
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import APIError, AuthenticationError, RateLimitError
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import (
    configure_logging,
    get_cors_origins,
    get_logger,
    get_max_request_body_size_bytes,
    get_model_id,
    is_production,
)
from .auth import get_current_user_id, require_auth
from .openai_client import get_client
from .prompts import CHEF_SYSTEM_PROMPT
from .schemas import (
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeBatchResult,
    AnalyzeRequest,
    AnalyzeResponse,
    DietaryProfileRequest,
    DietaryProfileResponse,
    MealAlternativeResult,
    NutritionEstimate,
    VoiceRequest,
    VoiceResponse,
)
from .tools import estimate_nutrition, find_nearby_stores

configure_logging()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter — per-IP, configurable via SNAPDISH_RATE_LIMIT env var
# Default: 60 requests/minute per IP (generous for mobile; tighten in prod)
# ---------------------------------------------------------------------------
_RATE_LIMIT = os.environ.get("SNAPDISH_RATE_LIMIT", "60/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[_RATE_LIMIT])

app = FastAPI(title="SnapDish API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: production requires SNAPDISH_CORS_ORIGINS (no wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

MAX_BODY_BYTES = get_max_request_body_size_bytes()


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup_validate() -> None:
    """Fail fast in production: validate API key is loadable from AWS Secrets."""
    if is_production():
        try:
            get_client()
        except Exception as e:
            logger.error("startup_validation_failed", extra={"error": str(e)})
            raise

    # Create DB tables if DB is configured (idempotent)
    try:
        from .db import create_all_tables
        create_all_tables()
    except Exception as exc:
        logger.warning("db_table_init_skipped", extra={"error": str(exc)})

    # Seed guardrail rules into DB (no-op if already seeded)
    try:
        from .guardrails import seed_guardrail_rules
        seed_guardrail_rules()
    except Exception as exc:
        logger.warning("guardrail_seed_error", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Request middleware: request-ID, body-size guardrail, structured logging
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_guardrails(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()

    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    logger.warning(
                        "request_body_too_large",
                        extra={
                            "request_id": request_id,
                            "path": request.url.path,
                            "content_length": int(content_length),
                            "max": MAX_BODY_BYTES,
                        },
                    )
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"},
                    )
            except ValueError:
                pass

    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json_text(resp) -> str:
    output_text = (getattr(resp, "output_text", None) or "").strip()
    if output_text:
        return output_text
    output = getattr(resp, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "output_text" and getattr(part, "text", None):
                return str(part.text).strip()
    return ""


def _build_input_content(req: AnalyzeRequest) -> list[dict]:
    input_content: list[dict] = []
    if req.user_text:
        input_content.append({"type": "input_text", "text": req.user_text})
    if req.location is not None:
        input_content.append(
            {
                "type": "input_text",
                "text": f"User location: lat={req.location.lat}, lng={req.location.lng}.",
            }
        )
    if req.image_base64:
        image_url = req.image_base64.strip()
        if not image_url.startswith("data:"):
            image_url = f"data:image/jpeg;base64,{image_url}"
        input_content.append(
            {"type": "input_image", "image_url": image_url, "detail": "auto"}
        )
    return input_content


def _openai_vision_nutrition_fallback(image_base64: str, model_id: str) -> NutritionEstimate:
    """
    Fallback: send the dish image to OpenAI's vision model to estimate macros.
    Uses OPENAI_API_KEY from AWS Secrets. https://api.openai.com, TLS verified.
    Triggered when Spoonacular key is absent or /recipes/estimateNutrients returns empty.
    """
    try:
        client = get_client()
        image_url = image_base64.strip()
        if not image_url.startswith("data:"):
            image_url = f"data:image/jpeg;base64,{image_url}"
        resp = client.responses.create(
            model=model_id,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "You are a nutrition estimator. Analyse the dish in the image "
                        "and return ONLY a JSON object with keys: "
                        "calories_kcal (int), protein_g (float), carbs_g (float), "
                        "fat_g (float). Estimate for one typical serving. JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": image_url, "detail": "low"},
                        {"type": "input_text", "text": "Estimate macros for this dish."},
                    ],
                },
            ],
            text={"format": {"type": "json_object"}},
            store=False,
            max_output_tokens=80,
        )
        raw = _extract_json_text(resp)
        data = json.loads(raw) if raw else {}
        logger.info("openai_vision_nutrition_fallback_ok")
        return NutritionEstimate(
            calories_kcal=int(data["calories_kcal"]) if data.get("calories_kcal") is not None else None,
            protein_g=data.get("protein_g"),
            carbs_g=data.get("carbs_g"),
            fat_g=data.get("fat_g"),
            disclaimer=(
                f"Estimated from image via OpenAI vision ({model_id}). "
                "Actual macros depend on portion size and preparation."
            ),
        )
    except Exception as exc:
        logger.warning("openai_vision_nutrition_fallback_failed", extra={"error": str(exc)})
        return NutritionEstimate(
            disclaimer="Nutrition estimation unavailable for this image."
        )


def _run_one_analyze(
    req: AnalyzeRequest,
    model_id: str,
    dietary_system_block: str = "",
) -> AnalyzeResponse:
    """Execute a single analyze. dietary_system_block is injected into developer content."""
    from .cache import TTL_ANALYZE_RESPONSE, cache_get, cache_set
    import hashlib

    # Compute a cache key over the request content + dietary profile
    cache_payload = json.dumps(
        {
            "u": req.user_text or "",
            "img": req.image_base64[:32] if req.image_base64 else "",
            "loc": req.location.model_dump() if req.location else None,
            "dp": hashlib.sha256(dietary_system_block.encode()).hexdigest()[:8],
            "m": model_id,
        },
        sort_keys=True,
    )
    ck = hashlib.sha256(cache_payload.encode()).hexdigest()[:32]
    cached = cache_get("analyze", ck)
    if cached:
        logger.info("analyze_cache_hit")
        try:
            return AnalyzeResponse.model_validate(cached)
        except Exception:
            pass  # stale / schema change; proceed to full request

    client = get_client()
    input_content = _build_input_content(req)
    if not input_content:
        raise ValueError("Provide at least one of: user_text, image_base64, location")

    # Build developer (system) content — dietary block is prepended and non-tamperable
    developer_content = ""
    if dietary_system_block:
        developer_content = dietary_system_block + "\n\n"
    developer_content += CHEF_SYSTEM_PROMPT

    # Guardrail: check user text BEFORE sending to model
    from .guardrails import GuardrailViolation, check_input, check_output
    if req.user_text:
        check_input(req.user_text)  # raises GuardrailViolation on non-food topics

    resp = client.responses.create(
        model=model_id,
        input=[
            {"role": "developer", "content": developer_content},
            {"role": "user", "content": input_content},
        ],
        store=False,
        safety_identifier=req.safety_identifier,
        max_output_tokens=1200,
        text={"format": {"type": "json_object"}},
    )
    raw = _extract_json_text(resp)
    if not raw:
        raise ValueError("Model returned no JSON text output")
    data = json.loads(raw)

    # Guardrail: check output text for policy violations
    if data.get("cooking_guidance"):
        data["cooking_guidance"] = check_output(data["cooking_guidance"], context="cooking_guidance")

    # Enrich: nearby stores from Google Places
    data.setdefault("nearby_stores", [])
    if req.location is not None and not data["nearby_stores"]:
        data["nearby_stores"] = [s.model_dump() for s in find_nearby_stores(req.location)]

    # Enrich: nutrition from USDA FDC (text-based fallback via dish name)
    if not data.get("nutrition") or not data["nutrition"].get("calories_kcal"):
        dish_name = data.get("dish_guess") or ""
        if not dish_name and data.get("detected_ingredients"):
            dish_name = data["detected_ingredients"][0].get("name", "")
        if dish_name:
            data["nutrition"] = estimate_nutrition(dish_name).model_dump()

    # Enrich: Spoonacular image nutrition estimation
    # Primary: POST https://api.spoonacular.com/recipes/estimateNutrients (SPOONACULAR_API_KEY)
    # Fallback: OpenAI vision — send image to gpt-4o with a nutrition prompt (OPENAI_API_KEY)
    if req.image_base64 and (
        not data.get("nutrition") or not data["nutrition"].get("calories_kcal")
    ):
        try:
            from .food_api import estimate_spoonacular_nutrition_from_image
            b64 = req.image_base64.strip()
            img_data = b64.split(",", 1)[1] if "," in b64 else b64
            image_bytes = base64.b64decode(img_data)
            spoon_nutrition = estimate_spoonacular_nutrition_from_image(image_bytes)
            if spoon_nutrition.calories_kcal is not None:
                data["nutrition"] = spoon_nutrition.model_dump()
                logger.info("spoonacular_image_nutrition_enriched")
            else:
                # Spoonacular returned no data — fall back to OpenAI vision
                data["nutrition"] = _openai_vision_nutrition_fallback(
                    req.image_base64, model_id
                ).model_dump()
        except Exception as exc:
            logger.warning("image_nutrition_enrichment_failed", extra={"error": str(exc)})
            # Any failure — try OpenAI vision as last resort
            try:
                data["nutrition"] = _openai_vision_nutrition_fallback(
                    req.image_base64, model_id
                ).model_dump()
            except Exception:
                pass

    if not data.get("nutrition"):
        data.setdefault("nutrition", {"disclaimer": "No dish identified for nutrition lookup."})

    result = AnalyzeResponse.model_validate(data)
    cache_set("analyze", ck, result.model_dump(), TTL_ANALYZE_RESPONSE)
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict:
    from .db import is_db_available
    return {"ok": True, "db": is_db_available()}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
@limiter.limit(_RATE_LIMIT)
def analyze(
    req: AnalyzeRequest,
    request: Request,
    user_id: str = Depends(require_auth),
) -> AnalyzeResponse:
    """
    Analyze a dish from text, image, and/or location.
    Requires Bearer token authentication.
    Dietary safety profile is loaded server-side — the client cannot override it.
    """
    if req.image_base64:
        s = req.image_base64.strip()
        if not s.startswith("data:"):
            try:
                base64.b64decode(s)
            except Exception as e:
                logger.warning("invalid_image_base64", extra={"error": str(e)})
                raise HTTPException(status_code=400, detail=f"Invalid image_base64: {e}")

    # Load server-side dietary profile (non-tamperable by client)
    from .dietary_service import build_dietary_safety_prompt, load_dietary_profile
    profile = load_dietary_profile(user_id)
    dietary_block = build_dietary_safety_prompt(profile)

    model_id = get_model_id()
    try:
        return _run_one_analyze(req, model_id, dietary_block)
    except ValueError as e:
        raise HTTPException(status_code=400 if "Provide at least" in str(e) else 502, detail=str(e))
    except (AuthenticationError, RateLimitError, APIError) as e:
        raise HTTPException(
            status_code=502,
            detail="OpenAI authentication failed" if isinstance(e, AuthenticationError) else str(e),
        )
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        # GuardrailViolation (and any other unexpected error)
        from .guardrails import GuardrailViolation
        if isinstance(e, GuardrailViolation):
            raise HTTPException(status_code=400, detail=e.message)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/v1/analyze/batch", response_model=AnalyzeBatchResponse)
@limiter.limit("20/minute")
def analyze_batch(
    body: AnalyzeBatchRequest,
    request: Request,
    user_id: str = Depends(require_auth),
) -> AnalyzeBatchResponse:
    """
    Batch analyze: up to 100 requests in one HTTP call.

    Enterprise design for ~1M daily users:
      - Dietary profile loaded ONCE per batch, not per item (saves DB round-trips).
      - ThreadPoolExecutor sized to: min(n, BATCH_WORKERS) where BATCH_WORKERS is
        tuned per instance type (default 20 — enough for I/O-bound OpenAI calls).
      - Semaphore caps concurrent OpenAI calls to BATCH_OPENAI_CONCURRENCY (default 10)
        to stay well within OpenAI's per-minute rate limits at scale.
      - Per-item cache means repeated items in a batch hit Redis, not the model.
      - Each item fails independently: one bad request does not cancel the batch.
      - Results returned in original submission order.

    For very large async workloads (>100 items), use OpenAI's native Batch API
    via the /v1/analyze/async-batch endpoint (24h SLA, 50% cost reduction).
    """
    import concurrent.futures
    import threading
    import os

    BATCH_WORKERS = int(os.environ.get("SNAPDISH_BATCH_WORKERS", "20"))
    BATCH_OPENAI_CONCURRENCY = int(os.environ.get("SNAPDISH_BATCH_OPENAI_CONCURRENCY", "10"))

    # Load dietary profile ONCE for the entire batch
    from .dietary_service import build_dietary_safety_prompt, load_dietary_profile
    profile = load_dietary_profile(user_id)
    dietary_block = build_dietary_safety_prompt(profile)

    model_id = get_model_id()
    n = len(body.requests)
    results: list[AnalyzeBatchResult] = [None] * n  # type: ignore[list-item]

    # Semaphore limits simultaneous OpenAI API calls to avoid 429s at scale
    semaphore = threading.Semaphore(BATCH_OPENAI_CONCURRENCY)

    def run_item(i: int, r: AnalyzeRequest) -> None:
        with semaphore:  # gate on OpenAI concurrency
            try:
                out = _run_one_analyze(r, model_id, dietary_block)
                results[i] = AnalyzeBatchResult(id=str(i), response=out, error=None)
            except Exception as e:
                results[i] = AnalyzeBatchResult(id=str(i), response=None, error=str(e))

    workers = min(n, max(BATCH_WORKERS, 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_item, i, r) for i, r in enumerate(body.requests)]
        concurrent.futures.wait(futures)  # wait for all; exceptions captured per-item

    logger.info("batch_analyze_complete", extra={"n": n, "workers": workers})
    return AnalyzeBatchResponse(results=results)


@app.post("/v1/meal/alternatives", response_model=list[MealAlternativeResult])
@limiter.limit(_RATE_LIMIT)
def meal_alternatives(
    request: Request,
    query: str,
    limit: int = 5,
    user_id: str = Depends(require_auth),
) -> list[MealAlternativeResult]:
    """
    Return safe meal alternatives for the authenticated user.
    Dietary constraints come from the server-side profile — client cannot inject their own.
    Backed by local DB + USDA FDC + Open Food Facts + Edamam + Nutritionix + MealDB + Spoonacular.
    Input is guardrail-checked: only food-related queries accepted.
    """
    from .dietary_service import load_dietary_profile
    from .guardrails import GuardrailViolation, check_input
    from .meal_repository import find_meal_alternatives

    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    limit = min(max(limit, 1), 8)

    # Guardrail: ensure query is food-related
    try:
        check_input(query)
    except GuardrailViolation as e:
        raise HTTPException(status_code=400, detail=e.message)

    profile = load_dietary_profile(user_id)

    alternatives = find_meal_alternatives(
        dish_name=query.strip()[:100],
        allergy_tags=profile.allergy_tags,
        restriction_tags=profile.restriction_tags,
        condition_tags=profile.condition_tags,
        limit=limit,
    )
    return [MealAlternativeResult(**a.as_dict()) for a in alternatives]


# --- Dietary profile management (authenticated users only) ---

@app.get("/v1/profile/dietary", response_model=DietaryProfileResponse)
def get_dietary_profile(
    request: Request,
    user_id: str = Depends(require_auth),
) -> DietaryProfileResponse:
    """Return the current user's dietary profile. Requires authentication."""
    from .dietary_service import load_dietary_profile
    profile = load_dietary_profile(user_id)
    return DietaryProfileResponse(
        user_id=user_id,
        allergy_tags=profile.allergy_tags,
        restriction_tags=profile.restriction_tags,
        condition_tags=profile.condition_tags,
        disliked_ingredients=profile.disliked_ingredients,
        preferred_cuisines=profile.preferred_cuisines,
        custom_notes=profile.custom_notes,
    )


@app.post("/v1/profile/dietary", response_model=DietaryProfileResponse, status_code=status.HTTP_200_OK)
def update_dietary_profile(
    body: DietaryProfileRequest,
    request: Request,
    user_id: str = Depends(require_auth),
) -> DietaryProfileResponse:
    """
    Create or update the current user's dietary profile. Requires authentication.
    Tags are validated server-side against the controlled vocabulary in models.py.
    Clients CANNOT send arbitrary constraint strings.
    """
    from .dietary_service import save_dietary_profile

    try:
        profile = save_dietary_profile(user_id, body.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return DietaryProfileResponse(
        user_id=user_id,
        allergy_tags=profile.allergy_tags,
        restriction_tags=profile.restriction_tags,
        condition_tags=profile.condition_tags,
        disliked_ingredients=profile.disliked_ingredients,
        preferred_cuisines=profile.preferred_cuisines,
        custom_notes=profile.custom_notes,
    )


# --- Voice API ---

VOICE_OUTPUT_SAMPLERATE = 24000


@app.post("/v1/voice", response_model=VoiceResponse)
@limiter.limit(_RATE_LIMIT)
async def voice(
    req: VoiceRequest,
    request: Request,
    user_id: str = Depends(require_auth),
) -> VoiceResponse:
    """
    Send audio (speech) and receive Chef Marco's voice response.
    Dietary profile is injected into the voice agent context server-side.
    Input: base64-encoded PCM mono 16-bit audio.
    Output: base64-encoded PCM mono 16-bit at 24 kHz.
    """
    import numpy as np

    from .voice_agent import build_chef_marco_voice_agent, get_voice_pipeline_config
    from agents.voice import AudioInput, SingleAgentVoiceWorkflow, VoicePipeline

    from .dietary_service import build_dietary_safety_prompt, load_dietary_profile
    profile = load_dietary_profile(user_id)
    dietary_block = build_dietary_safety_prompt(profile)

    try:
        raw = base64.b64decode(req.audio_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio_base64: {e}")

    buffer = np.frombuffer(raw, dtype=np.int16)
    if buffer.size == 0:
        raise HTTPException(status_code=400, detail="Empty audio buffer")

    agent = build_chef_marco_voice_agent(dietary_block=dietary_block)
    config = get_voice_pipeline_config()
    pipeline = VoicePipeline(
        workflow=SingleAgentVoiceWorkflow(agent),
        config=config,
    )
    audio_input = AudioInput(buffer=buffer)

    try:
        result = await pipeline.run(audio_input)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Voice pipeline error: {e!s}") from e

    response_chunks: list = []
    async for event in result.stream():
        if getattr(event, "type", None) == "voice_stream_event_audio":
            response_chunks.append(event.data)

    if not response_chunks:
        raise HTTPException(status_code=502, detail="Voice pipeline returned no audio")

    response_audio = np.concatenate(response_chunks, axis=0)
    out_bytes = response_audio.tobytes()
    return VoiceResponse(
        audio_base64=base64.b64encode(out_bytes).decode("ascii"),
        sample_rate=VOICE_OUTPUT_SAMPLERATE,
    )

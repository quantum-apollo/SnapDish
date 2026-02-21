from __future__ import annotations

import base64
import json
import os

from fastapi import FastAPI, HTTPException
from openai import APIError, AuthenticationError, RateLimitError
from pydantic import ValidationError

from .openai_client import get_client
from .prompts import CHEF_SYSTEM_PROMPT
from .schemas import (
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeBatchResult,
    AnalyzeRequest,
    AnalyzeResponse,
    VoiceRequest,
    VoiceResponse,
)
from .tools import estimate_nutrition_stub, find_nearby_stores


app = FastAPI(title="SnapDish API", version="0.1.0")


def _extract_json_text(resp) -> str:
    """Best-effort extraction of JSON text from a Responses API response."""

    output_text = (getattr(resp, "output_text", None) or "").strip()
    if output_text:
        return output_text

    # Fallback: walk output items.
    output = getattr(resp, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "output_text" and getattr(part, "text", None):
                return str(part.text).strip()

    return ""


def _build_input_content(req: AnalyzeRequest) -> list[dict]:
    """Build Responses API input content from AnalyzeRequest."""
    input_content: list[dict] = []
    if req.user_text:
        input_content.append({"type": "input_text", "text": req.user_text})
    if req.location is not None:
        input_content.append(
            {
                "type": "input_text",
                "text": f"User location provided: lat={req.location.lat}, lng={req.location.lng}.",
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


def _run_one_analyze(req: AnalyzeRequest, model_id: str) -> AnalyzeResponse:
    """Execute a single analyze against the Responses API. Used by single and batch endpoints."""
    client = get_client()
    input_content = _build_input_content(req)
    if not input_content:
        raise ValueError("Provide at least one of: user_text, image_base64, location")

    resp = client.responses.create(
        model=model_id,
        input=[
            {"role": "developer", "content": CHEF_SYSTEM_PROMPT},
            {"role": "user", "content": input_content},
        ],
        store=False,
        safety_identifier=req.safety_identifier,
        max_output_tokens=900,
        text={"format": {"type": "json_object"}},
    )
    raw = _extract_json_text(resp)
    if not raw:
        raise ValueError("Model returned no JSON text output")
    data = json.loads(raw)
    data.setdefault("nearby_stores", [])
    if req.location is not None and not data["nearby_stores"]:
        data["nearby_stores"] = [s.model_dump() for s in find_nearby_stores(req.location)]
    if not data.get("nutrition"):
        data["nutrition"] = estimate_nutrition_stub().model_dump()
    return AnalyzeResponse.model_validate(data)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Single analyze request. For many requests use POST /v1/analyze/batch or the Batch API script for 50% cost."""
    if req.image_base64:
        s = req.image_base64.strip()
        if not s.startswith("data:"):
            try:
                base64.b64decode(s)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=f"Invalid image_base64: {e}")
    model_id = os.environ.get("SNAPDISH_MODEL", "gpt-5.2")
    try:
        return _run_one_analyze(req, model_id)
    except ValueError as e:
        raise HTTPException(status_code=400 if "Provide at least" in str(e) else 502, detail=str(e))
    except (AuthenticationError, RateLimitError, APIError) as e:
        raise HTTPException(
            status_code=502,
            detail="OpenAI authentication failed (check OPENAI_API_KEY)" if isinstance(e, AuthenticationError) else str(e),
        )
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/v1/analyze/batch", response_model=AnalyzeBatchResponse)
def analyze_batch(body: AnalyzeBatchRequest) -> AnalyzeBatchResponse:
    """
    Run multiple analyze requests in parallel (same process). Results in one response.
    For 50% lower cost and async processing, use the OpenAI Batch API via scripts/batch_analyze.py.
    """
    import concurrent.futures

    model_id = os.environ.get("SNAPDISH_MODEL", "gpt-5.2")
    results: list[AnalyzeBatchResult] = []
    n = len(body.requests)

    def run_item(i: int, r: AnalyzeRequest) -> AnalyzeBatchResult:
        custom_id = str(i)
        try:
            out = _run_one_analyze(r, model_id)
            return AnalyzeBatchResult(id=custom_id, response=out, error=None)
        except Exception as e:  # noqa: BLE001
            return AnalyzeBatchResult(id=custom_id, response=None, error=str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(n, 10)) as executor:
        futures = [executor.submit(run_item, i, r) for i, r in enumerate(body.requests)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    # Preserve order by id (we used index as id)
    results.sort(key=lambda x: int(x.id))
    return AnalyzeBatchResponse(results=results)


# --- Voice: audio in → Chef Marco → audio out ---
VOICE_OUTPUT_SAMPLERATE = 24000


@app.post("/v1/voice", response_model=VoiceResponse)
async def voice(req: VoiceRequest) -> VoiceResponse:
    """
    Send audio (speech) and receive Chef Marco's voice response.

    Input: base64-encoded PCM mono 16-bit audio (e.g. from mic).
    Output: base64-encoded PCM mono 16-bit at 24 kHz for playback.
    """
    import numpy as np

    from .voice_agent import build_chef_marco_voice_agent, get_voice_pipeline_config
    from agents.voice import AudioInput, SingleAgentVoiceWorkflow, VoicePipeline

    try:
        raw = base64.b64decode(req.audio_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio_base64: {e}")

    buffer = np.frombuffer(raw, dtype=np.int16)
    if buffer.size == 0:
        raise HTTPException(status_code=400, detail="Empty audio buffer")

    agent = build_chef_marco_voice_agent()
    config = get_voice_pipeline_config()
    pipeline = VoicePipeline(
        workflow=SingleAgentVoiceWorkflow(agent),
        config=config,
    )
    audio_input = AudioInput(buffer=buffer)

    try:
        result = await pipeline.run(audio_input)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Voice pipeline error: {e!s}",
        ) from e

    response_chunks: list = []
    async for event in result.stream():
        if getattr(event, "type", None) == "voice_stream_event_audio":
            response_chunks.append(event.data)

    if not response_chunks:
        raise HTTPException(
            status_code=502,
            detail="Voice pipeline returned no audio",
        )

    response_audio = np.concatenate(response_chunks, axis=0)
    out_bytes = response_audio.tobytes()
    return VoiceResponse(
        audio_base64=base64.b64encode(out_bytes).decode("ascii"),
        sample_rate=VOICE_OUTPUT_SAMPLERATE,
    )

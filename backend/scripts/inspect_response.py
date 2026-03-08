#!/usr/bin/env python3
"""
Dev script: call OpenAI Responses API and log output. Uses AWS Secrets or env for OPENAI_API_KEY.
Run from repo root: python -m backend.scripts.inspect_response
Or from backend/: python scripts/inspect_response.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Ensure backend/snapdish is importable
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from snapdish.config import configure_logging, get_env, get_logger, get_secret
from openai import OpenAI

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set (set AWS_SECRET_NAME or OPENAI_API_KEY in env)")
        raise SystemExit("Missing OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)
    model_id = get_env("SNAPDISH_MODEL") or get_secret("SNAPDISH_MODEL") or "gpt-5.2"

    resp = client.responses.create(
        model=model_id,
        input=[
            {"role": "developer", "content": "Return JSON with key hello (string)."},
            {"role": "user", "content": "Say hi"},
        ],
        store=False,
        text={"format": {"type": "json_object"}},
        max_output_tokens=100,
    )

    logger.info("output_text: %s", repr(getattr(resp, "output_text", None)))
    logger.info("output: %s", resp.output)


if __name__ == "__main__":
    main()

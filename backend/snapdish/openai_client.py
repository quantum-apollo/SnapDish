from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


def get_client() -> OpenAI:
    # Loads repo-root .env for local dev.
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    return OpenAI(api_key=api_key)

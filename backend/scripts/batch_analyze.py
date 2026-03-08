#!/usr/bin/env python3
"""
Submit SnapDish analyze requests via the OpenAI Batch API for ~50% lower cost.

Usage:
  1. Create a JSONL file where each line is one request, e.g.:
     {"custom_id": "req-1", "user_text": "How do I make pasta carbonara?"}
     {"custom_id": "req-2", "user_text": "Suggest a quick salad", "location": {"lat": 40.7, "lng": -74.0}}
  2. Run: python scripts/batch_analyze.py batch_input.jsonl
  3. Script uploads the file, creates a batch (endpoint /v1/responses), and prints the batch ID.
  4. Poll status: python scripts/batch_analyze.py --poll <batch_id>
  5. Download results: python scripts/batch_analyze.py --download <batch_id> -o results.jsonl

Input JSONL fields (per line):
  - custom_id (required): unique string for this request
  - user_text (optional): user message
  - location (optional): {"lat": float, "lng": float}
  - image_url (optional): HTTPS URL to image (preferred; keeps file under 200MB)
  - image_base64 (optional): base64 string (avoid for many/large images)

Batch API: 50% cost discount, 24h SLA, higher rate limits. No streaming.
See: https://platform.openai.com/docs/guides/batch
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Allow importing from snapdish when run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from snapdish.config import configure_logging, get_env, get_logger, get_secret
from snapdish.prompts import CHEF_SYSTEM_PROMPT

configure_logging()
logger = get_logger(__name__)


def _build_input_content(row: dict) -> list[dict]:
    """Build Responses API input content from a row (custom_id, user_text, location, image_url or image_base64)."""
    content: list[dict] = []
    if row.get("user_text"):
        content.append({"type": "input_text", "text": row["user_text"]})
    loc = row.get("location")
    if loc and isinstance(loc, dict):
        lat, lng = loc.get("lat"), loc.get("lng")
        if lat is not None and lng is not None:
            content.append(
                {"type": "input_text", "text": f"User location provided: lat={lat}, lng={lng}."}
            )
    if row.get("image_url"):
        content.append(
            {"type": "input_image", "image_url": row["image_url"], "detail": "auto"}
        )
    elif row.get("image_base64"):
        b64 = row["image_base64"].strip()
        if not b64.startswith("data:"):
            b64 = f"data:image/jpeg;base64,{b64}"
        content.append({"type": "input_image", "image_url": b64, "detail": "auto"})
    return content


def build_batch_request_lines(input_jsonl_path: str, model: str) -> list[dict]:
    """Read input JSONL and return list of Batch API request objects (custom_id, method, url, body)."""
    requests = []
    with open(input_jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"Invalid JSON on line {i}: {e}")
            custom_id = row.get("custom_id")
            if not custom_id:
                raise SystemExit(f"Line {i}: missing 'custom_id'")
            content = _build_input_content(row)
            if not content:
                raise SystemExit(f"Line {i}: provide at least one of user_text, image_url, image_base64")
            body = {
                "model": model,
                "input": [
                    {"role": "developer", "content": CHEF_SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                "store": False,
                "max_output_tokens": 900,
                "text": {"format": {"type": "json_object"}},
            }
            if row.get("safety_identifier"):
                body["safety_identifier"] = row["safety_identifier"]
            requests.append({
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/responses",
                "body": body,
            })
    return requests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit SnapDish analyze via OpenAI Batch API (50% cost) or poll/download."
    )
    parser.add_argument(
        "input_file_or_batch_id",
        nargs="?",
        help="Path to input JSONL file to submit, or batch_id for --poll/--download",
    )
    parser.add_argument(
        "--model",
        default=get_env("SNAPDISH_MODEL") or get_secret("SNAPDISH_MODEL") or "gpt-5.2",
        help="Model ID (default: SNAPDISH_MODEL or gpt-5.2)",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Poll batch status until completed (or failed/expired).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download batch output file to JSONL.",
    )
    parser.add_argument(
        "-o", "--output",
        default="batch_output.jsonl",
        help="Output path for --download (default: batch_output.jsonl)",
    )
    args = parser.parse_args()

    api_key = get_secret("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY or AWS_SECRET_NAME with OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)

    if args.poll or args.download:
        if not args.input_file_or_batch_id:
            raise SystemExit("Provide batch_id when using --poll or --download")
        batch_id = args.input_file_or_batch_id
        batch = client.batches.retrieve(batch_id)
        logger.info("Batch %s status: %s", batch.id, batch.status)
        if args.poll and batch.status not in ("completed", "failed", "expired", "cancelled"):
            logger.info("Poll until completed; run again with --poll to re-check.")
            return
        if args.download and batch.status == "completed" and batch.output_file_id:
            content = client.files.content(batch.output_file_id)
            with open(args.output, "wb") as f:
                f.write(content.read())
            rc = getattr(batch, "request_counts", None)
            n = getattr(rc, "completed", None) if rc else None
            if n is None and isinstance(rc, dict):
                n = rc.get("completed", 0)
            n = n or 0
            logger.info("Wrote %s results to %s", n, args.output)
        elif args.download and batch.status != "completed":
            logger.warning("Batch not completed; no output to download.")
        return

    # Submit new batch
    if not args.input_file_or_batch_id:
        raise SystemExit("Provide input JSONL path. See script docstring for format.")
    input_path = args.input_file_or_batch_id
    if not Path(input_path).is_file():
        raise SystemExit(f"File not found: {input_path}")

    request_lines = build_batch_request_lines(input_path, args.model)
    batch_input_path = Path(input_path).with_name(Path(input_path).stem + "_batch_request.jsonl")
    with open(batch_input_path, "w", encoding="utf-8") as f:
        for r in request_lines:
            f.write(json.dumps(r) + "\n")
    logger.info("Wrote %s requests to %s", len(request_lines), batch_input_path)

    with open(batch_input_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/responses",
        completion_window="24h",
    )
    logger.info("Batch created: %s", batch.id)
    logger.info("Status: %s. Check: python scripts/batch_analyze.py --poll %s", batch.status, batch.id)
    logger.info("Download when done: python scripts/batch_analyze.py --download %s -o results.jsonl", batch.id)


if __name__ == "__main__":
    main()

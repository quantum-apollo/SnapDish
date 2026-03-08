#!/usr/bin/env python3
"""
seed_aws_secrets.py — Merge SnapDish API keys into AWS Secrets Manager.

Reads key/value pairs from a .env file (or --json string), maps them to the
canonical AWS secret key names used by the backend, and merges them into the
existing AWS secret (AWS_SECRET_NAME) without touching any already-present keys
unless --overwrite is passed.

Run this ONCE per environment to provision secrets. Safe to re-run (idempotent).

Usage
-----
# From workspace root with the venv active:
  python backend/scripts/seed_aws_secrets.py \\
      --env-file "mobile/React-Native-Snapchat-Clone/node_modules/.env" \\
      --secret-name snapdish/prod \\
      --region us-east-1

  # Or pass JSON directly:
  python backend/scripts/seed_aws_secrets.py \\
      --json '{"USDA_FDC_API_KEY": "XMHL5...", "SPOONACULAR_API_KEY": "a080e..."}' \\
      --secret-name snapdish/prod

AWS Credentials
---------------
Ensure the executing IAM identity has:
  secretsmanager:GetSecretValue
  secretsmanager:PutSecretValue
  secretsmanager:CreateSecret   (only if the secret doesn't yet exist)

Secret schema (what the backend reads via config.get_secret())
--------------------------------------------------------------
Key                         Description
--------------------------  ------------------------------------------------
OPENAI_API_KEY              OpenAI API key (set separately — NOT from .env)

# Edamam — Nutrition Analysis API (POST /api/nutrition-details)
EDAMAM_NUTRITION_APP_ID     App ID for Edamam Nutrition Analysis (32a0b829)
EDAMAM_NUTRITION_APP_KEY    App key for Edamam Nutrition Analysis

# Edamam — Recipe Search API (GET /api/recipes/v2)
EDAMAM_APP_ID               App ID for Edamam Recipe Search (cfa0c459)
EDAMAM_APP_KEY              App key for Edamam Recipe Search

# Edamam — Food Database API (GET /api/food-database/v2/parser)
# Falls back to EDAMAM_NUTRITION_APP_ID/KEY if not set separately.
EDAMAM_FOOD_APP_ID          App ID for Edamam Food Database
EDAMAM_FOOD_APP_KEY         App key for Edamam Food Database

# USDA FoodData Central
USDA_FDC_API_KEY            USDA FDC REST API key

# Spoonacular
SPOONACULAR_API_KEY         Spoonacular food/recipe API key

# Optional: search model override (defaults to gpt-4o-mini)
SNAPDISH_SEARCH_MODEL       e.g. gpt-4o-mini
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# .env file parser (minimal — only KEY=VALUE lines, strips comments)
# ---------------------------------------------------------------------------

_ENV_LINE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$")


def _parse_env_file(path: str) -> dict[str, str]:
    """Parse a .env file and return a flat dict of key → raw value."""
    result: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                # Strip inline comments (anything after first un-quoted #)
                code = re.split(r"\s+#", line, maxsplit=1)[0].strip()
                # Also strip trailing em-dash junk (as seen in the .env)
                code = re.sub(r"\s+[—–-]+\s*.*$", "", code)
                m = _ENV_LINE.match(code)
                if m:
                    key, val = m.group(1), m.group(2)
                    # Strip surrounding quotes
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    result[key] = val
    except FileNotFoundError:
        print(f"ERROR: .env file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return result


# ---------------------------------------------------------------------------
# Map from .env key names → canonical AWS secret key names
# ---------------------------------------------------------------------------

# Edamam has multiple API products with separate App IDs.
# The .env uses generic names; we map them to explicit product names so the
# backend can look up the right credentials per endpoint.
_ENV_TO_SECRET: dict[str, list[str]] = {
    # Edamam Nutrition Analysis API key
    # → used for POST https://api.edamam.com/api/nutrition-details
    # → also used as Food Database fallback
    "EDAMAM_NUTRITION_ANALYSIS_API_KEY": [
        "EDAMAM_NUTRITION_APP_KEY",
        "EDAMAM_FOOD_APP_KEY",   # fallback — same subscription covers food DB
    ],

    # Edamam Recipe Search API key
    # → used for GET https://api.edamam.com/api/recipes/v2
    "EDAMAM_RECIPE_SEARCH_API_KEY": [
        "EDAMAM_APP_KEY",
    ],

    # USDA FoodData Central
    "USDA_GOV_API_KEY": ["USDA_FDC_API_KEY"],

    # Spoonacular
    "SPOONACULAR_API_KEY": ["SPOONACULAR_API_KEY"],
}

# App IDs extracted from .env comments — hardcoded because the .env file
# embeds them in comment text, not as parseable KEY=VALUE pairs.
_STATIC_SECRETS: dict[str, str] = {
    "EDAMAM_NUTRITION_APP_ID": "32a0b829",   # Nutrition Analysis App ID
    "EDAMAM_FOOD_APP_ID": "32a0b829",        # Food DB fallback (same subscription)
    "EDAMAM_APP_ID": "cfa0c459",             # Recipe Search App ID
}


def _build_new_secrets(env_values: dict[str, str]) -> dict[str, str]:
    """Map parsed .env values + static App IDs to canonical AWS secret key names."""
    new: dict[str, str] = {}

    # Map dynamic keys
    for env_key, secret_keys in _ENV_TO_SECRET.items():
        val = env_values.get(env_key)
        if val:
            for sk in secret_keys:
                new[sk] = val
        else:
            print(f"  [SKIP] {env_key} not found in .env — keeping existing value", file=sys.stderr)

    # Add static App IDs
    new.update(_STATIC_SECRETS)
    return new


# ---------------------------------------------------------------------------
# AWS Secrets Manager helpers
# ---------------------------------------------------------------------------

def _get_current_secret(client: object, secret_name: str) -> dict[str, str]:
    from botocore.exceptions import ClientError  # type: ignore

    try:
        resp = client.get_secret_value(SecretId=secret_name)  # type: ignore[union-attr]
        raw = resp.get("SecretString") or "{}"
        return json.loads(raw)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ResourceNotFoundException":
            print(f"  Secret '{secret_name}' not found — will CREATE it.", file=sys.stderr)
            return {}
        raise


def _put_secret(
    client: object,
    secret_name: str,
    payload: dict[str, str],
    must_create: bool,
) -> None:
    if must_create:
        client.create_secret(  # type: ignore[union-attr]
            Name=secret_name,
            SecretString=json.dumps(payload),
            Description="SnapDish API secrets",
        )
        print(f"  Created secret '{secret_name}'.")
    else:
        client.put_secret_value(  # type: ignore[union-attr]
            SecretId=secret_name,
            SecretString=json.dumps(payload),
        )
        print(f"  Updated secret '{secret_name}'.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed SnapDish API keys into AWS Secrets Manager.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--env-file", help="Path to .env file to read keys from.")
    src.add_argument("--json", dest="json_str", help="Inline JSON string of key/value pairs.")
    parser.add_argument(
        "--secret-name",
        default=os.environ.get("AWS_SECRET_NAME", ""),
        help="AWS Secrets Manager secret name (default: $AWS_SECRET_NAME).",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: $AWS_REGION or us-east-1).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite keys that already exist in the secret. Default: merge (skip existing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without actually calling AWS.",
    )
    args = parser.parse_args()

    if not args.secret_name:
        print("ERROR: --secret-name or $AWS_SECRET_NAME required.", file=sys.stderr)
        sys.exit(1)

    # ── Source values ──────────────────────────────────────────────────────────
    if args.env_file:
        print(f"\nReading .env: {args.env_file}")
        raw_env = _parse_env_file(args.env_file)
    else:
        raw_env = json.loads(args.json_str)

    new_secrets = _build_new_secrets(raw_env)

    # ── Fetch existing secret ──────────────────────────────────────────────────
    try:
        import boto3  # type: ignore
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3", file=sys.stderr)
        sys.exit(1)

    client = boto3.client("secretsmanager", region_name=args.region)
    print(f"\nFetching existing secret: {args.secret_name} ({args.region})")
    existing = _get_current_secret(client, args.secret_name)
    must_create = not existing

    # ── Merge ─────────────────────────────────────────────────────────────────
    merged = dict(existing)
    added: list[str] = []
    skipped: list[str] = []

    for key, val in new_secrets.items():
        if key in merged and not args.overwrite:
            skipped.append(key)
        else:
            merged[key] = val
            added.append(key)

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\nKeys to ADD/UPDATE ({len(added)}):")
    for k in sorted(added):
        redacted = merged[k][:4] + "..." if len(merged[k]) > 4 else "***"
        print(f"  {k} = {redacted}")

    if skipped:
        print(f"\nKeys SKIPPED — already exist (use --overwrite to replace) ({len(skipped)}):")
        for k in sorted(skipped):
            print(f"  {k}")

    if not added:
        print("\nNothing to update.")
        return

    # ── Write ─────────────────────────────────────────────────────────────────
    if args.dry_run:
        print("\n[DRY RUN] Would write the following secret payload to AWS:")
        safe_payload = {k: (v[:4] + "...") for k, v in merged.items()}
        print(json.dumps(safe_payload, indent=2))
    else:
        print(f"\nWriting to AWS Secrets Manager: {args.secret_name}")
        _put_secret(client, args.secret_name, merged, must_create)
        print("\nDone. Backend will read these via config.get_secret().")
        print(
            "\nNext: restart the backend so the new secrets are picked up "
            "(or use --hot-reload if supported)."
        )


if __name__ == "__main__":
    main()

# SnapDish Backend (FastAPI)

Production-first, enterprise standards: API key from AWS Secrets Manager only; no localhost or .env in production; batch for throughput.

## Setup
1) Create and activate a virtualenv
- `py -3.12 -m venv backend\.venv`
- `backend\.venv\Scripts\Activate.ps1`

2) Install deps
- `pip install -r backend/requirements.txt`

3) Production config (required for production)
- **AWS_SECRET_NAME** – Secret name in AWS Secrets Manager. Secret must be JSON with `OPENAI_API_KEY` (e.g. `{"OPENAI_API_KEY": "sk-..."}`). The API key is read only from Secrets; no env or .env fallback.
- **SNAPDISH_CORS_ORIGINS** – Comma-separated allowed origins (e.g. `https://app.snapdish.com`). No wildcard in production.
- **SNAPDISH_LOG_JSON=1** – Use for CloudWatch (structured JSON logs).
- Optional: `SNAPDISH_MODEL`, `AWS_REGION`, `SNAPDISH_MAX_BODY_MB`, `SNAPDISH_MAX_BATCH_SIZE`.

## Run
- `python -m uvicorn backend.snapdish.main:app --reload --port 8000`

## Endpoints
- `POST /v1/analyze` – analyze a dish from text + optional image + optional location
- `POST /v1/analyze/batch` – run up to 100 analyze requests in parallel (one response)
- `POST /v1/voice` – send base64 PCM audio, get Chef Marco’s voice response (base64 PCM, 24 kHz)
- `GET /healthz`

## Batch (recommended for multiple requests)

**Option 1: Same-request batch** — `POST /v1/analyze/batch` with `{ "requests": [ {...}, ... ] }`. Use for high throughput: one shared OpenAI client; up to 100 per call.

**Option 2: OpenAI Batch API (50% cost discount)** — For non-urgent bulk jobs, use the script via the [Batch API](https://platform.openai.com/docs/guides/batch): 50% cheaper, higher rate limits, results within 24 hours.

1. Create a JSONL file with one request per line, e.g.  
   `{"custom_id": "req-1", "user_text": "How do I make carbonara?"}`  
   Optional fields: `location` (`{"lat": 40.7, "lng": -74}`), `image_url` (HTTPS; preferred over base64 to keep file under 200MB), `image_base64`, `safety_identifier`.

2. From the **backend** directory:  
   `python scripts/batch_analyze.py batch_input.jsonl`  
   This uploads the file, creates a batch (endpoint `/v1/responses`), and prints the batch ID.

3. Poll status:  
   `python scripts/batch_analyze.py --poll <batch_id>`

4. Download results when completed:  
   `python scripts/batch_analyze.py --download <batch_id> -o results.jsonl`  

Output lines match input order by `custom_id`; each line has `response.body` with the model output (JSON). No streaming; batch runs asynchronously on OpenAI’s side.

## Real-time voice assistant
Chef Marco runs as a **multi-agent voice assistant** (mic → STT → triage → specialist agent → TTS → speaker) using the [OpenAI Agents SDK voice pipeline](https://developers.openai.com/cookbook/examples/agents_sdk/app_assistant_voice_agents).

**Agents:**
- **Triage (Chef Marco)** – welcomes the user and routes to:
- **Knowledge Agent** – recipes, ingredients, cooking steps, product tips, substitutions (optional vector store via `SNAPDISH_VECTOR_STORE_ID`).
- **Account Agent** – account balance, membership (stub; plug in your auth/account API).
- **Search Agent** – web search for **locations for food products**, where to buy ingredients, nearby stores, trending info.

1. Install voice extras (included in `requirements.txt`):  
   `pip install "openai-agents[voice]" numpy sounddevice`

2. From the **backend** directory, run:  
   `python scripts/voice_assistant.py`

3. Press **Enter** to start recording, speak your question, then press **Enter** again to send. Type `esc` to exit.

Requires a working microphone and speakers. Uses `OPENAI_API_KEY` and optional `SNAPDISH_MODEL` (default for voice: `gpt-4o-mini`). Optional: `SNAPDISH_VECTOR_STORE_ID` (comma-separated) for Knowledge Agent file search.

**HTTP voice API** (`POST /v1/voice`): send JSON `{ "audio_base64": "<base64 PCM mono 16-bit>", "sample_rate": 24000 }`; response is `{ "audio_base64": "<base64>", "sample_rate": 24000 }`. Use this from mobile or web to record → send → play response.

## Commerce (ChatGPT Instant Checkout)

SnapDish can sell through **ChatGPT** via the [Agentic Commerce Protocol](https://agenticcommerce.dev) (Instant Checkout). See **docs/COMMERCE.md** for the protocol overview, implementation checklist (product feed, Checkout API, webhooks, Delegated Payment), and links to the [Agentic Checkout Spec](https://developers.openai.com/commerce/specs/checkout) and [Product feeds](https://developers.openai.com/commerce/product-feeds). Request/response stubs for checkout sessions live in **snapdish/commerce_schemas.py**.

## Developer references (voice, agents, Realtime, evals)

See **docs/DEVELOPER_NOTES.md** for curated links and short summaries: Realtime API (GA, WebRTC/WebSocket, idle timeouts, migration), Skills + Shell + Compaction, 15 lessons building ChatGPT Apps, and testing agent skills with evals.

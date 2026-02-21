# SnapDish — Directory tree & file descriptions

Concise overview of the repo. **Vision** is used in the API and prompts; **commerce** is documented for ChatGPT Instant Checkout (Agentic Commerce Protocol).

```
SnapDish/
├── .gitignore
├── STRUCTURE.md              # This file: directory tree + short descriptions
├── TODO.md                   # Per-file checklist: endpoints and tasks to complete (fill in later)
│
├── docs/
│   ├── CHAT_UI.md            # Chat UI (mobile-first): nearby restaurant listings, enriched discovery, rounded corners, chat at bottom
│   ├── COMMERCE.md           # Agentic Commerce Protocol, Instant Checkout (ChatGPT), implementation checklist
│   ├── DEVELOPER_NOTES.md    # Curated OpenAI refs: Realtime API, Skills/Shell/Compaction, ChatGPT Apps, Evals for skills
│   ├── FRONTEND_TEMPLATES.md # OpenAI + mobile UI templates: ChatKit, Pizzaz, Tamagui/NativeUI (better than Material for mobile)
│   ├── MOBILE_APP.md         # iOS/Android app: Expo stack, app structure, backend API, checklist
│   ├── PRODUCT_FEED.md      # Product feed onboarding, delivery, field reference, best practices
│   └── PROMPTING_RESOURCES.md # Prompting libs, evals tools, guides, videos, papers (reasoning/CoT)
│
├── mobile/                   # Expo (React Native) app — iOS & Android, one codebase
│   ├── app/                  # Expo Router: _layout, (tabs)/index (chat), (tabs)/settings
│   ├── src/api/client.ts     # analyze(), voice(), base URL from Settings
│   ├── package.json
│   └── README.md             # Run, switch UI template (Tamagui/NativeUI), next steps
│
├── examples/
│   └── chat-ui/              # Mobile-first reference: chat + restaurant cards (rounded), input at bottom, safe areas (see docs/CHAT_UI.md)
│       ├── index.html
│       ├── styles.css
│       └── README.md
│
├── backend/
│   ├── README.md             # Setup, run, endpoints, voice assistant, HTTP voice API
│   ├── requirements.txt     # FastAPI, OpenAI, openai-agents[voice], numpy, sounddevice
│   ├── run.ps1              # Start API (creates venv if needed, uvicorn on port 8000)
│   ├── test_analyze.ps1      # Script to hit POST /v1/analyze (e.g. test vision + text)
│   │
│   ├── scripts/
│   │   ├── batch_analyze.py       # OpenAI Batch API: submit JSONL for 50% cost (analyze)
│   │   ├── inspect_response.py   # Dev: call Responses API with JSON mode, print output
│   │   └── voice_assistant.py    # CLI: mic → Chef Marco voice pipeline → speaker
│   │
│   └── snapdish/
│       ├── __init__.py
│       ├── main.py           # FastAPI app: /healthz, /v1/analyze, /v1/analyze/batch, /v1/voice
│       ├── openai_client.py  # OpenAI client from OPENAI_API_KEY (.env)
│       ├── prompts.py        # CHEF_SYSTEM_PROMPT (vision rules, JSON output schema)
│       ├── schemas.py        # Pydantic: AnalyzeRequest/Response, VoiceRequest/Response, etc.
│       ├── commerce_schemas.py   # Pydantic stubs for Agentic Checkout (sessions, line items, fulfillment)
│       ├── tools.py          # Stubs: find_nearby_stores, estimate_nutrition_stub, build_grocery_list
│       └── voice_agent.py    # Multi-agent voice: triage → Knowledge / Account / Search agents
│
└── prompts/
    ├── chef_marco_system.md  # Long-form Chef Marco prompt; vision/image workflow, safety
    ├── model_settings.md     # Suggested model params (temperature, safety, formatting)
    └── usage_example.py      # Example: load prompt from MD, call Responses API (text-only)
```

---

## Vision capabilities

SnapDish uses **vision (image input)** with the Responses API for dish/ingredient analysis and cooking guidance.

| Where | What |
|-------|------|
| **POST /v1/analyze** | Accepts `image_base64` (optional) with `user_text` and/or `location`. Model sees the image and returns structured JSON: detected ingredients, cooking guidance, alternatives, grocery list, safety notes. |
| **prompts.py** | `CHEF_SYSTEM_PROMPT` includes vision handling: detect ingredients from image, confidence levels, up to 3 confirmation questions, checkpoint-based guidance. |
| **chef_marco_system.md** | Full vision/image workflow: “What I see”, confirm, next action; real-time guidance via new images at key moments. |
| **schemas.py** | `AnalyzeRequest.image_base64`; `AnalyzeResponse.detected_ingredients` (name, confidence, notes). |

**Vision + function calling** (e.g. image → choose action: suggest_recipe, find_stores, escalate): use a vision-capable model with tool/function definitions and `tool_choice` (or instructor/Pydantic for structured tool output). Cookbook pattern: image in user message + `response_model` (e.g. `RefundOrder | ReplaceOrder | EscalateToAgent`) or tools; instructor `Mode.PARALLEL_TOOLS` or Responses API. See [GPT-4o Vision with function calling](https://developers.openai.com/cookbook/examples/multimodal/using_gpt4_vision_with_function_calling); **docs/DEVELOPER_NOTES.md** has the full pattern, plus Flex processing and reasoning-model guidance.

---

## Commerce capabilities (ChatGPT Instant Checkout)

SnapDish can sell through **ChatGPT** using the **Agentic Commerce Protocol** (Instant Checkout): users buy from you inside ChatGPT; you keep the customer relationship, orders, and payments.

| Where | What |
|-------|------|
| **docs/COMMERCE.md** | Overview of the protocol, Instant Checkout, and implementation checklist (product feed, Checkout API, webhooks, Delegated Payment, certify). |
| **backend/snapdish/commerce_schemas.py** | Pydantic stubs for checkout session request/response types (Address, Item, LineItem, FulfillmentOption, Totals, Messages, etc.) aligned with the [Agentic Checkout Spec](https://developers.openai.com/commerce/specs/checkout). |
| **Backend API** | When implementing: add REST endpoints for create/update/complete/cancel/get checkout sessions and webhooks for order events; mount under e.g. `/commerce` and use `commerce_schemas`. |

To go live: apply at [chatgpt.com/merchants](https://chatgpt.com/merchants), provide a product feed, implement the Checkout API and Delegated Payment (e.g. Stripe), then certify with OpenAI.

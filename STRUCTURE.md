
# SnapDish — Directory tree & file descriptions

This file documents the actual directory structure and provides a concise description of every file and folder, including extra and missing items compared to the original plan. Auto-generated and empty folders are noted but not described in detail.

## Root

```
SnapDish/
├── .env                  # Environment variables (local, not in VCS)
├── .gitignore            # Git ignore rules
├── STRUCTURE.md          # This file: directory tree + short descriptions
├── TODO.md               # Per-file checklist: endpoints and tasks to complete
├── run-local.ps1         # PowerShell script to run the project locally
├── _backup/              # (Empty) Placeholder for backups
├── .venv/                # Python virtual environment (auto-generated)
├── node_modules/         # Node.js dependencies (auto-generated)
│
├── backend/              # FastAPI backend for SnapDish
│   ├── README.md             # Documentation for backend setup, endpoints, and usage. (90% ready)
│   ├── requirements.txt      # Python dependencies (FastAPI, OpenAI, etc.). (95% ready)
│   ├── run.ps1               # PowerShell script to start the API. (90% ready)
│   ├── test_analyze.ps1      # Script to test the analyze endpoint. (40% ready)
│   ├── scripts/              # Utility scripts for batch processing, debugging, and voice assistant.
│   │   ├── batch_analyze.py      # Bulk analysis via OpenAI Batch API. (80% ready)
│   │   ├── inspect_response.py   # Dev script to call Responses API and print output. (30% ready)
│   │   └── voice_assistant.py    # CLI for real-time voice assistant (mic input, agent pipeline). (50% ready)
│   └── snapdish/             # Main backend code for SnapDish API and agent logic.
│       ├── __init__.py           # Package marker for snapdish module. (100% ready)
│       ├── cache.py              # Enterprise caching layer: Redis primary, thread-safe in-memory LRU fallback. (100% ready)
│       ├── db.py                 # SQLAlchemy 2.x engine, session factory, create_all_tables(). (100% ready)
│       ├── models.py             # ORM models: User, UserDietaryProfile, CachedMeal, CachedIngredient, GuardrailRule + controlled vocabulary frozensets. (100% ready)
│       ├── guardrails.py         # Code-level guardrails: input/output/search enforcement, DB-backed rules, seed_guardrail_rules(). (100% ready)
│       ├── food_api.py           # 7-source food API integrations: USDA FDC, Open Food Facts, Edamam (recipe+food), Nutritionix, TheMealDB, Spoonacular — parallel search with caching. (100% ready)
│       ├── meal_repository.py    # Tiered meal alternatives (cache → DB → APIs → persist) and ingredient nutrition lookup. (100% ready)
│       ├── dietary_service.py    # Server-side dietary profile: JWT extraction, profile CRUD, non-tamperable safety prompt builder. (100% ready)
│       ├── main.py               # FastAPI app: health, analyze, batch, voice, meal alternatives, dietary profile endpoints. Guardrails wired on all text endpoints. (100% ready)
│       ├── openai_client.py      # Loads OpenAI API key and returns a client. (90% ready)
│       ├── prompts.py            # Chef Marco system prompt: multicultural, multimodal, dietary-safe, food-only guardrail. (100% ready)
│       ├── schemas.py            # Pydantic models: Analyze, Voice, DietaryProfile, MealAlternative. (100% ready)
│       ├── commerce_schemas.py   # Pydantic models for commerce/checkout (Agentic Commerce Protocol). (90% ready)
│       ├── tools.py              # Real store lookup (Google Places), USDA FDC nutrition, haversine distance. (100% ready)
│       ├── voice_agent.py        # Multi-agent voice pipeline: triage, knowledge (real tools), account, search (guardrail-gated food_web_search). (100% ready)
│       └── __pycache__/          # Python bytecode cache (auto-generated)
│           ├── main.cpython-312.pyc           # Compiled bytecode for main.py
│           ├── openai_client.cpython-312.pyc  # Compiled bytecode for openai_client.py
│           ├── prompts.cpython-312.pyc        # Compiled bytecode for prompts.py
│           ├── schemas.cpython-312.pyc        # Compiled bytecode for schemas.py
│           ├── tools.cpython-312.pyc          # Compiled bytecode for tools.py
│           └── __init__.cpython-312.pyc       # Compiled bytecode for __init__.py
│
├── docs/                   # Documentation and design notes
│   ├── CHAT_UI.md              # Chat UI design and data shape
│   ├── COMMERCE.md             # Agentic Commerce Protocol and implementation
│   ├── DEVELOPER_NOTES.md      # OpenAI references, agent skills, and evals
│   ├── FRONTEND_TEMPLATES.md   # UI templates and recommendations
│   ├── MOBILE_APP.md           # Mobile app structure, stack, and API
│   ├── PRODUCT_FEED.md         # Product feed onboarding and field reference
│   └── PROMPTING_RESOURCES.md  # Prompting tools, guides, and papers
│
├── examples/
│   └── chat-ui/              # Mobile-first chat UI mockup (HTML/CSS)
│       ├── index.html            # Example chat UI with enriched discovery block
│       ├── styles.css            # Mobile-first CSS for chat UI
│       └── README.md             # How to use the chat UI example
│
├── mobile/                  # Expo (React Native) app — iOS & Android, one codebase
│   ├── README.md                # How to run and customize the mobile app
│   ├── TEMPLATE_SOURCE.md       # UI template and icon source documentation
│   ├── app.json                 # Expo app config
│   ├── babel.config.js          # Babel config for React Native
│   ├── eas.json                 # EAS build config
│   ├── tamagui.config.ts        # Tamagui UI config (optional)
│   ├── tsconfig.json            # TypeScript config
│   ├── assets/                  # (Empty) Placeholder for assets
│   ├── snapdish/                # (Empty) Placeholder for future code
│   ├── src/
│   │   └── api/
│   │       └── client.ts            # API client for analyze/voice endpoints
│   └── React-Native-Snapchat-Clone/ # Full-featured Expo React Native app (not in original plan)
│       ├── app/                      # Expo Router structure for screens and navigation
│       ├── assets/                   # Fonts and images
│       ├── components/               # UI components (camera, chat, navigation, etc.)
│       ├── constants/                # Color themes
│       ├── hooks/                    # Custom React hooks
│       ├── scripts/                  # Project reset script
│       ├── src/api/                  # API client and initialization
│       ├── tsconfig.json, babel.config.js, etc. # Project configs
│       └── node_modules/             # Node.js dependencies (auto-generated)
│
├── prompts/                 # Prompt and model settings
│   ├── chef_marco_system.md     # Chef Marco’s long-form prompt
│   ├── model_settings.md        # Model parameter suggestions
│   └── usage_example.py         # Example of loading a prompt and calling the API
```

---

## Notes on Extra/Missing Items

- **Extra:** `.env`, `.venv/`, `node_modules/`, `_backup/`, `.expo/`, `__pycache__/`, `__tests__/`, and snapshot folders are present but not part of the main codebase. Some folders are empty or auto-generated.
- **Missing in original STRUCTURE.md:** The `mobile/React-Native-Snapchat-Clone/` subproject and its internal structure, as well as some config/scripts, are now documented above.

---

## Concise Descriptions (by folder)

**Root:**
- `.gitignore` — Git ignore rules.
- `STRUCTURE.md` — Directory tree and file descriptions.
- `TODO.md` — Per-file checklist and tasks.
- `run-local.ps1` — PowerShell script to run the project locally.
- `_backup/` — (Empty) Placeholder for backups.
- `.env` — Local environment variables (not in VCS).
- `.venv/` — Python virtual environment (auto-generated).
- `node_modules/` — Node.js dependencies (auto-generated).

**backend/**
- `README.md` — Backend setup, endpoints, and usage.
- `requirements.txt` — Python dependencies (FastAPI, OpenAI, etc.).
- `run.ps1` — PowerShell script to start the API.
- `test_analyze.ps1` — Script to test the analyze endpoint.
- `scripts/` — Utility scripts for batch, dev, and voice assistant tasks.
- `snapdish/` — Main backend code: FastAPI app, OpenAI client, prompts, schemas, commerce, tools, and voice agent.
- `__pycache__/` — Python bytecode cache (auto-generated).

**docs/**
- `CHAT_UI.md` — Chat UI design and data shape.
- `COMMERCE.md` — Agentic Commerce Protocol and implementation.
- `DEVELOPER_NOTES.md` — OpenAI references, agent skills, and evals.
- `FRONTEND_TEMPLATES.md` — UI templates and recommendations.
- `MOBILE_APP.md` — Mobile app structure, stack, and API.
- `PRODUCT_FEED.md` — Product feed onboarding and field reference.
- `PRODUCTION_READINESS.md` — Production readiness review: backend/frontend overview, gaps, and checklists.
- `PROMPTING_RESOURCES.md` — Prompting tools, guides, and papers.

**examples/chat-ui/**
- `index.html` — Mobile-first chat UI mockup.
- `styles.css` — Mobile-first CSS for chat UI.
- `README.md` — How to use the chat UI example.

**mobile/**
- `README.md` — How to run and customize the mobile app.
- `TEMPLATE_SOURCE.md` — UI template and icon source documentation.
- `app.json`, `babel.config.js`, `eas.json`, `tamagui.config.ts`, `tsconfig.json` — Expo and TypeScript configs.
- `assets/` — (Empty) Placeholder for assets.
- `snapdish/` — (Empty) Placeholder for future code.
- `src/api/client.ts` — API client for analyze/voice endpoints.
- `React-Native-Snapchat-Clone/` — Full-featured Expo React Native app (see below).

**mobile/React-Native-Snapchat-Clone/**
- `app/` — Expo Router structure for screens and navigation.
- `assets/` — Fonts and images.
- `components/` — UI components (camera, chat, navigation, etc.).
- `constants/` — Color themes.
- `hooks/` — Custom React hooks.
- `scripts/` — Project reset script.
- `src/api/` — API client and initialization.
- `tsconfig.json`, `babel.config.js`, etc. — Project configs.
- `node_modules/` — Node.js dependencies (auto-generated).

**prompts/**
- `chef_marco_system.md` — Chef Marco’s long-form prompt.
- `model_settings.md` — Model parameter suggestions.
- `usage_example.py` — Example of loading a prompt and calling the API.

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

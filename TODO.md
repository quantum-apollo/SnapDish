# SnapDish — TODO by file

Check off items as you complete them. Add notes or sub-tasks under each item if needed.

## Current Priorities (2026)

- [ ] Implement and polish live camera preview in mobile app (expo-camera)
- [ ] Integrate real map view in Maps tab (react-native-maps)
- [ ] Add voice recording and playback (connect to /v1/voice)
- [ ] Render nearby restaurants/stores in Feed/Maps (from API)
- [ ] Polish chat UI: safe areas, touch targets, enriched cards
- [ ] Add custom app icon and splash (SnapDish branding)
- [ ] Prepare for Play Store deployment (EAS config, app.json, assets)
- [ ] Complete backend commerce endpoints and product feed for ChatGPT Instant Checkout

---

## backend/snapdish/main.py

**Existing endpoints (production-ready, accomplished):**
- [x] `GET /healthz`
- [x] `POST /v1/analyze` (vision + text + location)
- [x] `POST /v1/voice` (audio in → Chef Marco audio out)

**Endpoints to add:**
- [ ] **Commerce:** `POST /checkout_sessions` — create session; return 201 + full cart state (use `commerce_schemas`)
- [ ] **Commerce:** `POST /checkout_sessions/{checkout_session_id}` — update session; return full cart state
- [ ] **Commerce:** `POST /checkout_sessions/{checkout_session_id}/complete` — complete with payment_data; create order; return state + optional Order
- [ ] **Commerce:** `POST /checkout_sessions/{checkout_session_id}/cancel` — cancel session; return 405 if already completed/canceled
- [ ] **Commerce:** `GET /checkout_sessions/{checkout_session_id}` — get session; return 404 if not found
- [ ] (Optional) **Vision + function calling:** e.g. `POST /v1/analyze/actions` — image + optional text → structured tool/action response (per cookbook pattern)

**Other:**
- [ ] Mount commerce routes (e.g. under `/commerce` or at root per spec); add request validation and error responses (`CheckoutErrorResponse` on 4xx/5xx)
- [ ] Commerce: verify request headers (Authorization, Idempotency-Key, Signature, etc.) and echo response headers (Idempotency-Key, Request-Id)

---

## backend/snapdish/commerce_schemas.py

**Status:** Schemas defined per Agentic Checkout Spec. (production-ready)

**To do:**
- [ ] Extend `ErrorCode` / `CheckoutErrorResponse` if spec adds more error codes
- [ ] Add any merchant-specific fields (e.g. custom Message codes) if needed
- [ ] (Optional) Add Pydantic validators for Total/LineItem consistency rules from spec

---

## backend/snapdish/voice_agent.py

**Status:** Triage + Knowledge + Account + Search agents and handoffs implemented. (production-ready)

**To do:**
- [ ] Replace `_get_account_info_stub` with real account API (or wire to your auth/user service)
- [ ] (Optional) Add `SNAPDISH_VECTOR_STORE_ID` and use `FileSearchTool` in Knowledge agent for product/recipe docs
- [ ] (Optional) Add more tools to Knowledge or Search agents (e.g. product lookup by id for commerce)
- [ ] (Optional) Voice: add support for image input in pipeline if you want “send photo + voice” in one turn

---

## backend/snapdish/schemas.py

**Status:** AnalyzeRequest/Response, VoiceRequest/Response, commerce in commerce_schemas.py. (production-ready)

**To do:**
- [ ] Add any new request/response models here if you add new API surface (e.g. vision+actions, product feed webhook body)
- [ ] (Optional) Add strict response schema for `/v1/analyze` (e.g. json_schema structured output) and align with schemas.py

---

## backend/snapdish/tools.py

**Status:** Stubs for stores and nutrition. (in progress)

**To do:**
- [ ] Replace `find_nearby_stores` with real provider (Google Places, Mapbox, Yelp, etc.)
- [ ] Replace `estimate_nutrition_stub` with real nutrition source (e.g. USDA/FDC-based API)
- [ ] (Optional) Add commerce-related helpers (e.g. get product by id, validate item availability) for checkout session logic

---

## backend/snapdish/prompts.py

**Status:** `CHEF_SYSTEM_PROMPT` with vision and JSON output. (production-ready)

**To do:**
- [ ] (Optional) Add a separate system prompt for vision + function calling if you add `/v1/analyze/actions`
- [ ] Tune prompt for production (safety, tone, output length)

---

## backend/snapdish/openai_client.py

**Status:** Returns OpenAI client from env. (production-ready)

**To do:**
- [ ] (Optional) Add a second client or config for commerce webhook signing (e.g. HMAC key from OpenAI)
- [ ] No endpoint work in this file

---

## docs/COMMERCE.md

**Status:** Protocol overview, key concepts, Checkout Spec summary, checklist.

**To do:**
- [ ] Document your base URL and webhook endpoint once deployed (for OpenAI config)
- [ ] Add “How we sign webhooks” (HMAC header name and key source) when you implement outbound webhooks

---

## Commerce (cross-file)

**Endpoints (implement in main.py or a dedicated router):**
- [ ] `POST /checkout_sessions` — create
- [ ] `POST /checkout_sessions/{id}` — update
- [ ] `POST /checkout_sessions/{id}/complete` — complete
- [ ] `POST /checkout_sessions/{id}/cancel` — cancel
- [ ] `GET /checkout_sessions/{id}` — get

**Webhooks (your server → OpenAI):**
- [ ] Implement outbound webhook: send `order_created` / `order_updated` to OpenAI-provided URL; sign with HMAC (header e.g. `Merchant_Name-Signature`)
- [ ] (Optional) If OpenAI calls you for webhook config: document or implement receiver/verification

**Product feed:** (See **docs/PRODUCT_FEED.md** and **Product feed** section below.)
- [ ] Define product catalog (ids, titles, pricing, inventory, media) per Product Feed Spec
- [ ] Implement feed generation as `jsonl.gz` or `csv.gz` (UTF-8); stable filename; overwrite on each run
- [ ] Submit initial sample (~100 items, all required fields) for validation
- [ ] Deliver full snapshot via SFTP, file upload, or hosted URL per onboarding; at least daily cadence

**Payments:**
- [ ] Integrate Delegated Payment (e.g. Stripe Shared Payment Token); accept token in `/complete` and charge via your PSP
- [ ] Handle decline/retry and return appropriate Message/error to ChatGPT

**Security & certify:**
- [ ] Authenticate all checkout requests; verify Signature header per spec
- [ ] Enforce idempotency using Idempotency-Key
- [ ] Pass OpenAI conformance checks and get production access

---

## prompts/ (chef_marco_system.md, model_settings.md, usage_example.py)

**To do:**
- [ ] (Optional) Add a “commerce” or “product recommendation” section to chef_marco_system.md if Chef Marco should suggest purchasable products
- [ ] usage_example.py: update model id or add vision example if needed
- [ ] No endpoints in this folder

---

## backend/scripts/

**Status:** inspect_response.py (dev), voice_assistant.py (CLI voice).

**To do:**
- [ ] (Optional) Add script to call commerce endpoints (e.g. create session, update, complete) for local testing
- [ ] (Optional) Add script to generate or validate product feed
- [ ] No new endpoints; scripts are for dev/testing

---

## STRUCTURE.md

**To do:**
- [ ] When commerce router or new endpoints exist, add them to the directory tree and endpoint list
- [ ] No endpoint implementation in this file

---

## Product feed (docs/PRODUCT_FEED.md)

**Onboarding:** [Apply](https://chatgpt.com/merchants) for access first (approved partners only).

**Implementation path:**
- [ ] Review [Product Feed Spec](https://developers.openai.com/commerce/product-feeds/spec); confirm field names, required attributes, formats
- [ ] Validate required fields on every row before delivery
- [ ] Deliver full snapshot via SFTP, file upload, or hosted URL (per onboarding)

**Feed format & delivery:**
- [ ] Output format: `jsonl.gz` or `csv.gz`; encoding UTF-8
- [ ] Use a **stable file name**; overwrite same file on each update (no new name per run)
- [ ] If sharding: keep shard set stable; replace same shard files each update; ≤500k items per shard, target &lt;500 MB per shard
- [ ] Cadence: at least daily (no intraday price/availability updates)

**Required fields (ensure present every row):**
- [ ] OpenAI flags: `is_eligible_search`, `is_eligible_checkout`
- [ ] Basic: `item_id`, `title`, `description`, `url`
- [ ] Item: `brand`
- [ ] Media: `image_url`
- [ ] Price: `price` (number + ISO 4217 currency)
- [ ] Availability: `availability`
- [ ] Variants: `group_id`, `listing_has_variations`
- [ ] Merchant: `seller_name`, `seller_url`; if checkout eligible: `seller_privacy_policy`, `seller_tos`
- [ ] Returns: `return_policy`
- [ ] Geo: `target_countries`, `store_country`

**Optional but recommended:** `variant_dict`, size/color, reviews/Q&A, shipping, performance signals, compliance (warning, age_restriction). See **docs/PRODUCT_FEED.md** and the [spec](https://developers.openai.com/commerce/product-feeds/spec).

**Quality & best practices:**
- [ ] Add UTM (e.g. `utm_medium=feed`) to `url` for feed attribution if needed
- [ ] Removals: set `is_eligible_search=false` or omit from next snapshot
- [ ] Follow [best practices](https://developers.openai.com/commerce/product-feeds/best-practices) (content, seller, variants, delivery)
- [ ] Ensure no prohibited products (see PRODUCT_FEED.md)

**File/script to implement:** (e.g. `backend/scripts/generate_product_feed.py` or a scheduled job that writes to the delivery location.)

- [ ] Implement feed export from catalog (DB/API) to spec-compliant rows
- [ ] Validate sample (e.g. 100 rows) then run full snapshot
- [ ] Automate daily (or desired cadence) and push to OpenAI delivery channel

---

## Chat UI — Nearby restaurant listings (mobile-first, enriched discovery)

**SnapDish is a mobile-first application** (native or hybrid), not web-first. **Goal:** Show nearby restaurant listings inside the chat in a card layout with rounded corners and chat input at the bottom ([blog reference](https://developers.openai.com/blog/what-makes-a-great-chatgpt-app)).

**Docs:** **docs/CHAT_UI.md** — mobile-first design, layout, safe areas, touch targets, data shape.  
**Example:** **examples/chat-ui/** — mobile-first HTML/CSS reference to translate into your native/hybrid app.

**To do:**
- [ ] Implement chat screen in your **mobile app** (React Native, Flutter, SwiftUI, etc.): scrollable messages + fixed input bar with **safe-area-inset-bottom**
- [ ] When API returns nearby places (`nearby_stores` / `nearby_restaurants`), render **enriched discovery block** (rounded container + cards) in the message list
- [ ] Use **≥44 pt/dp** touch targets for cards and send button; respect safe areas (notch, home indicator)
- [ ] (Optional) Backend: add `nearby_restaurants` or richer place fields (image_url, rating, cuisine) for card content

---

## Summary checklist

| Area              | Endpoints / work to complete |
|-------------------|------------------------------|
| **main.py**       | 5 commerce REST endpoints; optional vision+actions; headers & errors |
| **commerce_schemas.py** | Optional spec tweaks and validators |
| **voice_agent.py**| Replace account stub; optional vector store, tools, image-in-voice |
| **schemas.py**    | New models only if new API surface |
| **tools.py**      | Real stores + nutrition (and optional commerce helpers) |
| **Commerce**      | Webhooks, product feed, payments, auth, certify |
| **docs/COMMERCE.md** | Base URL, webhook signing |
| **docs/PRODUCT_FEED.md** | Onboarding path, delivery, required fields, best practices (done); add catalog-specific notes if needed |
| **Product feed** | Sample → full snapshot; jsonl.gz/csv.gz; stable filename; daily cadence; required fields; feed export script/job |
| **docs/CHAT_UI.md** | Mobile-first chat UI: nearby restaurant listings, enriched discovery, rounded corners, safe areas, touch targets |
| **examples/chat-ui** | Mobile-first HTML/CSS reference; translate into native/hybrid app (React Native, Flutter, etc.) |
| **Scripts**       | Optional: commerce test script; **feed generator** (export catalog to spec-compliant feed) |

Fill in dates, assignees, or sub-tasks under each checkbox as you go.

# SnapDish — Production readiness review

This document summarizes the codebase (from **STRUCTURE.md**, **TODO.md**, and architecture docs) and gives a concrete checklist to move **backend** and **frontend** to production. Use it with **TODO.md** for per-file tasks.

---

## 1. Codebase overview

### 1.1 Backend (FastAPI)

| Location | Purpose |
|----------|---------|
| **backend/snapdish/main.py** | FastAPI app: `GET /healthz`, `POST /v1/analyze`, `POST /v1/analyze/batch`, `POST /v1/voice`. Vision + text + location; batch runs in-process; voice uses Agents SDK pipeline. |
| **backend/snapdish/schemas.py** | Pydantic: `AnalyzeRequest`/`AnalyzeResponse`, `VoiceRequest`/`VoiceResponse`, batch types, `GeoLocation`, `StoreSuggestion`, `NutritionEstimate`, etc. |
| **backend/snapdish/commerce_schemas.py** | Pydantic models for Agentic Checkout (Item, Address, Buyer, LineItem, CheckoutSession, webhooks). No routes yet. |
| **backend/snapdish/prompts.py** | `CHEF_SYSTEM_PROMPT` — vision, JSON output schema, safety rules. |
| **backend/snapdish/openai_client.py** | Loads `OPENAI_API_KEY` from env (dotenv); returns OpenAI client. |
| **backend/snapdish/tools.py** | **Stubs:** `find_nearby_stores`, `estimate_nutrition_stub`, `build_grocery_list`. Intended to be replaced by real providers. |
| **backend/snapdish/voice_agent.py** | Multi-agent voice: Triage (Chef Marco) → Knowledge / Account / Search. Uses Agents SDK; account/stores/nutrition are stubs. |
| **backend/scripts/batch_analyze.py** | OpenAI Batch API: submit JSONL, poll, download results (50% cost discount). |
| **backend/scripts/voice_assistant.py** | CLI voice assistant (mic → pipeline → speaker). |
| **backend/README.md** | Setup, endpoints, batch, voice, commerce pointer. |

**Config / env:** `.env` at repo root (not in VCS); `OPENAI_API_KEY` required; optional `SNAPDISH_MODEL` (default `gpt-5.2`).

### 1.2 Frontend (mobile — Expo / React Native)

| Location | Purpose |
|----------|---------|
| **mobile/app/** | Expo Router: root `_layout.tsx` (PaperProvider, Stack), `index.tsx` → redirect to `/(tabs)`. |
| **mobile/app/(tabs)/** | Five tabs: **feed**, **maps**, **camera**, **chat**, **profile**. Tab bar uses MaterialCommunityIcons; camera tab centered. |
| **mobile/app/(tabs)/feed.tsx** | Discover feed: cards with avatar, location, icon placeholders (MaterialCommunityIcons). |
| **mobile/app/(tabs)/maps.tsx** | Nearby restaurants list + map placeholder (ready for react-native-maps). |
| **mobile/app/(tabs)/camera.tsx** | Photo capture/gallery via expo-image-picker; “Analyze with Chef Marco” (analyze not wired with base64 yet). |
| **mobile/app/(tabs)/chat.tsx** | Chat UI: messages, Chef Marco, calls `POST /v1/analyze` via API client. |
| **mobile/app/(tabs)/profile.tsx** | Welcome/login placeholder; Settings (API base URL in AsyncStorage). |
| **mobile/src/api/client.ts** | `analyze()`, `voice()`, `setApiBaseUrl` / `getApiBaseUrl`; base URL from Settings. |
| **mobile/app.json** | Expo config: name, slug, iOS bundleId `com.snapdish.app`, Android package `com.snapdish.app`, EAS projectId. |
| **mobile/eas.json** | EAS Build: development, preview, production (autoIncrement); submit production. |
| **mobile/TEMPLATE_SOURCE.md** | Documents: Material UI (React Native Paper + MaterialCommunityIcons) only; no custom icons. |

**Config:** API base URL is user-configurable in app (Profile → Settings); stored in AsyncStorage. No API keys in client; backend holds `OPENAI_API_KEY`.

### 1.3 Docs and references

- **STRUCTURE.md** — Directory tree, file roles, vision/commerce notes.
- **TODO.md** — Per-file checklists (commerce endpoints, tools, feed, chat UI, product feed, etc.).
- **docs/MOBILE_APP.md** — Mobile stack, backend API table, implementation checklist.
- **docs/COMMERCE.md** — Agentic Commerce, Instant Checkout, implementation checklist.
- **docs/PRODUCT_FEED.md** — Product feed onboarding, delivery, required fields.
- **docs/CHAT_UI.md** — Mobile-first chat, enriched discovery (nearby restaurants), safe areas, data shape.
- **docs/DEVELOPER_NOTES.md** — Realtime, agents, function calling, cost (Flex, batch).
- **docs/FRONTEND_TEMPLATES.md** — ChatKit, Apps SDK, mobile UI options.

---

## 2. What is production-ready today

- **Backend:** Health check, single and batch analyze, voice endpoint; schemas and commerce schemas defined; prompts and OpenAI client in place. Safe to deploy behind a URL with `OPENAI_API_KEY` and (optionally) `SNAPDISH_MODEL`.
- **Mobile:** Run on device/simulator; chat calls analyze; profile stores API URL; five-tab layout; Material UI template only. EAS project ID and bundle IDs set for store builds.
- **Scripts:** Batch API script and voice CLI usable for dev/batch jobs.
- **Secrets:** `.env` and `.gitignore` keep env out of VCS; no keys in mobile app.

---

## 3. What is not production-ready (gaps)

### Backend

1. **Commerce** — No checkout routes. TODO: implement `POST /checkout_sessions`, update, complete, cancel, `GET /checkout_sessions/{id}`; request/response validation; headers (Authorization, Idempotency-Key, Signature); webhooks (order_created/order_updated, HMAC). See **TODO.md** and **docs/COMMERCE.md**.
2. **Tools** — `find_nearby_stores` and `estimate_nutrition_stub` are stubs. Replace with real providers (e.g. Google Places / Mapbox / Yelp; USDA or nutrition API).
3. **Voice agent** — Account agent uses stub; optional vector store and extra tools not wired. Replace account stub with real auth/account API for production.
4. **Config** — No explicit production config (e.g. CORS, rate limits, request size limits). Add as needed for your host (e.g. reverse proxy, env-based CORS origin).
5. **Model** — Default `gpt-5.2`; confirm model ID and error handling for your OpenAI account/region.

### Frontend

1. **API base URL** — Production-only: no localhost. Set `EXPO_PUBLIC_API_URL` in EAS (or `extra.BACKEND_URL` in app config) for builds; users can override in Settings. App fails with a clear message if API URL is not configured.
2. **Camera → analyze** — Camera screen does not send `image_base64` to `POST /v1/analyze`; wire capture/gallery to request body.
3. **Voice** — No recording/playback in app; `voice()` exists in client but no UI. Add mic button → record → `POST /v1/voice` → play.
4. **Maps** — Placeholder only; integrate `react-native-maps` and (optionally) backend or third-party places data.
5. **Feed/Maps data** — Feed and maps use local placeholder data; replace with API (e.g. `nearby_stores` / `nearby_restaurants` from analyze or dedicated places endpoint).
6. **Chat UI** — Enriched discovery (restaurant cards in chat) and safe-area polish per **docs/CHAT_UI.md** not fully implemented (cards in chat, 44 pt targets).
7. **Assets** — Custom app icon and splash not set; add for store submission.
8. **Store deployment** — EAS config present; complete store listings, privacy policy, and store-specific requirements (e.g. permissions rationale).

### Commerce (cross-cutting)

- Product feed: not implemented (format, delivery, required fields per **docs/PRODUCT_FEED.md**).
- Payments: Delegated Payment (e.g. Stripe) not integrated.
- Certify with OpenAI for Instant Checkout and document base URL and webhook signing in **docs/COMMERCE.md**.

---

## 4. Backend production checklist

- [ ] **Env:** Set `OPENAI_API_KEY` (and optionally `SNAPDISH_MODEL`) in production environment; never commit `.env`.
- [ ] **CORS:** Backend uses `CORSMiddleware`; origins come from env `SNAPDISH_CORS_ORIGINS` (comma-separated; default `*`). For production set e.g. `https://yourapp.com,https://api.yourapp.com`.
- [ ] **Deploy:** Run with `uvicorn` (or ASGI host) and reverse proxy (HTTPS, optional rate limit). Example: `uvicorn snapdish.main:app --host 0.0.0.0 --port 8000` (adjust host/port for your host).
- [ ] **Health:** Use `GET /healthz` for load balancer or readiness checks.
- [ ] **Stubs:** Replace `find_nearby_stores` and `estimate_nutrition_stub` with real providers when you need real data.
- [ ] **Voice:** Replace account stub in `voice_agent.py` with real account API if voice is in scope for launch.
- [ ] **Commerce (if shipping Instant Checkout):** Implement checkout endpoints, webhooks, product feed, payments, then certify. See **TODO.md** and **docs/COMMERCE.md**.

---

## 5. Frontend (mobile) production checklist

- [ ] **API URL:** Decide production default (e.g. build-time env or in-app default) and document in **mobile/README.md**.
- [ ] **Camera → analyze:** Send selected/captured image as `image_base64` in `POST /v1/analyze`.
- [ ] **Voice:** Add record → `POST /v1/voice` → play response in app.
- [ ] **Maps:** Add `react-native-maps` and real data (from analyze or places API).
- [ ] **Feed / chat cards:** Use `nearby_stores` / `nearby_restaurants` from API; render enriched discovery blocks per **docs/CHAT_UI.md**.
- [ ] **Safe areas & touch targets:** Confirm 44 pt/dp and safe-area insets (already partially in place).
- [ ] **App icon & splash:** Add assets and reference in `app.json` for store builds.
- [ ] **EAS Build:** Run `eas build --platform all --profile production` (or per platform); fix any signing/config errors.
- [ ] **Store submission:** Prepare store listings, privacy policy, and permissions; use `eas submit` or manual upload.

---

## 6. Recommended order of work (for production)

1. **Backend live:** Deploy backend with `OPENAI_API_KEY`; set CORS; confirm `GET /healthz` and `POST /v1/analyze` from the app.
2. **Mobile → backend:** Set production API URL (or default in build); verify chat and (when wired) camera analyze end-to-end.
3. **Camera + voice:** Wire camera to `image_base64`; add voice record/playback.
4. **Real data:** Replace store/nutrition stubs; add maps and feed/chat data from API.
5. **Polish:** Enriched chat cards, safe areas, icon/splash.
6. **Commerce (if applicable):** Checkout API, feed, payments, webhooks, certify; document in **docs/COMMERCE.md** and **TODO.md**.

---

## 7. File structure quick reference

- **Backend:** `backend/snapdish/*.py` (main, schemas, commerce_schemas, prompts, openai_client, tools, voice_agent); `backend/scripts/*.py`.
- **Mobile:** `mobile/app/**` (Expo Router), `mobile/src/api/client.ts`, `mobile/app.json`, `mobile/eas.json`.
- **Docs:** `STRUCTURE.md`, `TODO.md`, `docs/*.md` (MOBILE_APP, COMMERCE, PRODUCT_FEED, CHAT_UI, DEVELOPER_NOTES, FRONTEND_TEMPLATES, PRODUCTION_READINESS).
- **Config:** Root `.env` (backend); mobile API URL in AsyncStorage (user Settings).

This review is based on **STRUCTURE.md**, **TODO.md**, **backend/README.md**, **docs/MOBILE_APP.md**, **docs/COMMERCE.md**, **docs/CHAT_UI.md**, **docs/PRODUCT_FEED.md**, and the current backend and mobile code. Update this doc as you complete items and add new endpoints or features.

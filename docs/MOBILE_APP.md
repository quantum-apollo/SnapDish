# SnapDish mobile app — iOS and Android

SnapDish is a **mobile app for iOS and Android**, with one codebase. This doc covers target platforms, recommended stack, app structure, and how the app talks to the SnapDish backend.

---

## Target platforms

| Platform | Target |
|----------|--------|
| **iOS** | iPhone (iOS 13+); support notch and safe areas. |
| **Android** | Phone (API 21+); support system bars and gesture navigation. |

Design **mobile-first**: single-column layout, touch targets ≥ 44 pt/dp, safe areas (see [CHAT_UI.md](CHAT_UI.md)).

---

## Recommended stack: Expo (React Native)

Use **Expo** (React Native) for one codebase that runs on both iOS and Android:

- **One codebase** — TypeScript/JavaScript, shared UI and logic.
- **Fast iteration** — `npx expo start` and run on simulator or device.
- **Native builds** — EAS Build for App Store and Play Store when ready.
- **Fits the backend** — Backend is FastAPI; mobile calls `POST /v1/analyze`, `POST /v1/voice`, and optional `POST /v1/analyze/batch`.

**Alternatives:** Flutter (Dart) or separate native apps (Swift, Kotlin) if you prefer; the backend and docs stay the same.

---

## App structure (suggested)

| Area | Purpose |
|------|---------|
| **Chat** | Main screen: messages, Chef Marco replies, enriched blocks (e.g. restaurant cards). Input at bottom; optional voice and camera buttons. |
| **Camera / photo** | Capture or pick image for dish/ingredient analysis; send to `POST /v1/analyze` with `image_base64` (+ optional `user_text`, `location`). |
| **Voice** | Record audio → send to `POST /v1/voice` → play response (base64 PCM 24 kHz). Or use Realtime API for low-latency speech-to-speech (see [DEVELOPER_NOTES.md](DEVELOPER_NOTES.md)). |
| **Map / places** | Optional: show nearby restaurants on a map or as list; data from analyze response `nearby_stores` / `nearby_restaurants` (see [CHAT_UI.md](CHAT_UI.md)). |
| **Settings** | API base URL (e.g. your deployed backend), auth placeholder, notifications. |

---

## Backend API (what the app uses)

| Endpoint | Method | Use |
|----------|--------|-----|
| **/v1/analyze** | POST | Send text and/or image (and optional location); get cooking guidance, ingredients, grocery list, nearby stores, nutrition. |
| **/v1/voice** | POST | Send base64 PCM audio; get Chef Marco’s voice response (base64 PCM, 24 kHz). |
| **/v1/analyze/batch** | POST | Optional: send multiple analyze requests in one call (e.g. for offline queue). |
| **/healthz** | GET | Check backend is up. |

Request/response shapes: **backend/snapdish/schemas.py** and **backend/README.md**.

---

## Implementation checklist

- [ ] **Create app** — Use the `mobile/` Expo scaffold in this repo (or `npx create-expo-app` and copy in API client and screens).
- [ ] **Chat screen** — Scrollable messages + fixed input at bottom; safe areas; min 44 pt/dp touch targets (see [CHAT_UI.md](CHAT_UI.md)).
- [ ] **Analyze** — Call `POST /v1/analyze` with `user_text` and optionally `image_base64`, `location`; show `AnalyzeResponse` (guidance, cards, grocery list).
- [ ] **Voice** — Mic button → record → `POST /v1/voice` → play response; or integrate Realtime API for streaming voice.
- [ ] **Camera / gallery** — Pick or capture image, optionally compress; attach to analyze request.
- [ ] **Enriched blocks** — Render `nearby_stores` / `nearby_restaurants` as cards (rounded, image, name, address, distance) inside the chat.
- [ ] **Config** — API base URL (dev vs prod); no API keys in the app (use backend proxy or signed tokens if needed).
- [ ] **Build for stores** — EAS Build for iOS and Android; follow App Store and Play Store guidelines.

---

## Mobile UI template (better than Material UI)

The app in `mobile/` is scaffolded with **React Native Paper** (Material 3) so it runs out of the box. For a **more native, mobile-suited** look (not Material), use **Tamagui** or **NativeUI** — see [FRONTEND_TEMPLATES.md](FRONTEND_TEMPLATES.md#mobile-ui-templates-ios--android--better-than-material-ui) and `mobile/README.md` (“Switching UI template”).

## Where things live

| Item | Location |
|------|----------|
| **Mobile app** | `mobile/` — Expo (React Native) app; run with `npx expo start`. |
| **Backend** | `backend/` — FastAPI; run with `uvicorn` (see backend/README.md). |
| **Chat UI spec** | [CHAT_UI.md](CHAT_UI.md) — Layout, safe areas, touch targets, data shape for cards. |
| **Templates / widgets** | [FRONTEND_TEMPLATES.md](FRONTEND_TEMPLATES.md) — ChatKit, Apps SDK, **mobile UI (Tamagui, NativeUI)**. |
| **API reference** | [backend/README.md](../backend/README.md) — Endpoints, voice, batch. |

---

## Running the mobile app

From the repo root:

```bash
cd mobile
npm install
npx expo start
```

Then press `i` for iOS simulator or `a` for Android emulator, or scan the QR code with Expo Go on a device. Set the API base URL (e.g. your machine’s IP and port for the backend) so the app can reach `POST /v1/analyze` and `POST /v1/voice`.

# Front-end templates — minimize custom code

OpenAI provides **templates and UI kits** so you can build the front end with as little custom code as possible. This doc maps official options to what SnapDish needs: **maps**, **chatbot**, **ecommerce-style widgets/icons**, and **video + voice buttons**. For the **mobile app** (iOS/Android), see **Mobile UI templates** below and [MOBILE_APP.md](MOBILE_APP.md).

---

## What SnapDish needs

| Need | Description |
|------|--------------|
| **Chatbot** | Chat UI with messages, streaming, tool results. |
| **Maps** | Show nearby restaurants/stores (e.g. map view or list with location). |
| **Ecommerce widgets/icons** | Cards, lists, buttons, badges for products/restaurants, checkout-style flows. |
| **Video** | Capture or upload video (e.g. dish photo/video for Chef Marco). |
| **Voice** | Button to record and send voice; play back AI voice (e.g. Chef Marco). |

---

## Official OpenAI templates and what they include

### 1. ChatKit + ChatKit Starter App (recommended for “chat + widgets” in your own product)

**What it is:** A **production-ready chat framework** with built-in streaming, tool/workflow integration, and **rich widgets** (cards, lists, buttons, images, etc.). You embed ChatKit in **your** app (web or mobile), and it works with either an OpenAI-hosted backend or your own (e.g. SnapDish FastAPI).

| SnapDish need | In ChatKit? | Notes |
|---------------|-------------|--------|
| **Chatbot** | ✅ | Core use case: messages, streaming, attachments. |
| **Maps** | ⚠️ | No built-in map widget. Use a **Card** or **Box** and embed your own map (e.g. Mapbox/Google Maps iframe or native component). |
| **Ecommerce widgets** | ✅ | **Card**, **ListView**, **Button**, **Badge**, **Image**, **Caption**, **Row/Col**, **DatePicker**, etc. [Widget Builder](https://widgets.chatkit.studio) to design and copy JSON. |
| **Video** | ⚠️ | **Attachments**: file/image upload. For “take video” you add a **button** that opens camera and uploads the file via your backend (ChatKit handles displaying/attaching). |
| **Voice** | ⚠️ | No built-in voice widget. Add a **voice button** that records audio, sends to `POST /v1/voice`, and plays the response (see backend). |

- **Starter:** [openai/openai-chatkit-starter-app](https://github.com/openai/openai-chatkit-starter-app) — clone and customize.
- **Widgets:** [ChatKit widgets](https://platform.openai.com/docs/guides/chatkit-widgets) · [Widget Builder](https://widgets.chatkit.studio) · [Widget actions](https://developers.openai.com/api/docs/guides/chatkit-actions).
- **Docs:** [ChatKit](https://developers.openai.com/api/docs/guides/chatkit) · [Custom theming](https://developers.openai.com/api/docs/guides/chatkit-themes).

Use this when you want the **chatbot + widget UI** in your own app (web or hybrid) with minimal custom UI code; you only add map embed, voice button, and video capture/upload.

---

### 2. Apps SDK examples — Pizzaz & kitchen_sink (ChatGPT Apps: inside ChatGPT)

**What it is:** Apps that run **inside ChatGPT** (MCP server + widgets). **Pizzaz** is the main demo: list view, carousel, **map view**, **checkout**, and interactive flows. **kitchen_sink** shows a broad set of components.

| SnapDish need | In Apps SDK / Pizzaz? | Notes |
|---------------|------------------------|--------|
| **Chatbot** | ✅ | ChatGPT is the chat; your app provides tools and widgets. |
| **Maps** | ✅ | Pizzaz includes a **map view** (e.g. store/restaurant locations). |
| **Ecommerce** | ✅ | **Checkout page**, list/carousel, product-style cards — good reference for ecommerce and Instant Checkout. |
| **Video** | ⚠️ | File upload via `openai/getFileUpload` / `uploadFile`; add a “record video” button that uploads. |
| **Voice** | ⚠️ | ChatGPT has its own voice; for Chef Marco voice you’d use a custom flow or Realtime. |

- **Examples:** [Apps SDK Examples](https://developers.openai.com/apps-sdk/build/examples) · [openai-apps-sdk-examples](https://github.com/openai/openai-apps-sdk-examples) (Pizzaz Node/Python, kitchen_sink, shopping_cart, etc.).
- **UI:** [UI guidelines](https://developers.openai.com/apps-sdk/concepts/ui-guidelines) · [Build your ChatGPT UI](https://developers.openai.com/apps-sdk/build/chatgpt-ui). The Apps SDK has a **UI Kit** (Tailwind-based) for consistent look.

Use this when you want the app to **live inside ChatGPT** (Discover/Apps). Clone Pizzaz or kitchen_sink and adapt for restaurants, maps, and commerce; add video upload and any custom voice flow.

---

### 3. Voice (separate from chat templates)

Voice is not part of the chat widget templates; you add it yourself:

- **SnapDish backend:** `POST /v1/voice` — send base64 PCM audio, get Chef Marco’s reply as base64 audio. Your front end needs a **voice button** that: record → send → play response.
- **Realtime API:** For low-latency speech-to-speech in the client, use [Realtime API](https://developers.openai.com/api/docs/guides/realtime) (WebRTC/WebSocket) or [Voice agents quickstart](https://openai.github.io/openai-agents-js/guides/voice-agents/quickstart/). Same idea: a button starts/stops the session and handles audio I/O.

So: **templates give you chat + widgets**; you add a **voice button** and wire it to either `/v1/voice` or Realtime.

---

## Recommendation for SnapDish (code as little as possible)

1. **Choose one base template**
   - **Your own app (web or mobile):** Start from **ChatKit Starter App**. You get chatbot + widgets (cards, lists, buttons, icons) out of the box. Use the [Widget Builder](https://widgets.chatkit.studio) for ecommerce-style cards and lists.
   - **App inside ChatGPT:** Start from **Pizzaz** (or kitchen_sink) in [openai-apps-sdk-examples](https://github.com/openai/openai-apps-sdk-examples). You get chatbot (ChatGPT) + **map view** + **checkout** + list/carousel; align with [UI guidelines](https://developers.openai.com/apps-sdk/concepts/ui-guidelines) and the Apps SDK UI Kit.

2. **Add only what’s missing**
   - **Maps (ChatKit):** One custom block: embed Mapbox or Google Maps inside a ChatKit Card/Box (or use a list of cards with addresses + “Open in Maps” link).
   - **Maps (Apps SDK):** Reuse Pizzaz **map view** pattern for restaurant locations.
   - **Ecommerce:** Use ChatKit **Card**/ **ListView**/ **Button**/ **Badge** (or Pizzaz checkout/list/carousel); no need to build from scratch.
   - **Video:** A **button** that opens camera, records/selects video, uploads via your API or file-upload flow; templates already support attachments/file input.
   - **Voice:** A **button** that toggles recording and calls `POST /v1/voice` (or Realtime); play response with your platform’s audio API.

3. **Mobile-first**  
   If the app is mobile (native/hybrid), use ChatKit or your chosen template in a mobile shell (e.g. React Native, Capacitor) and keep **touch targets ≥ 44 pt/dp** and **safe areas** as in [CHAT_UI.md](CHAT_UI.md).

---

## Quick links

| Resource | URL |
|----------|-----|
| ChatKit | [developers.openai.com/api/docs/guides/chatkit](https://developers.openai.com/api/docs/guides/chatkit) |
| ChatKit Starter App | [github.com/openai/openai-chatkit-starter-app](https://github.com/openai/openai-chatkit-starter-app) |
| ChatKit Widget Builder | [widgets.chatkit.studio](https://widgets.chatkit.studio) |
| ChatKit widgets guide | [platform.openai.com/docs/guides/chatkit-widgets](https://platform.openai.com/docs/guides/chatkit-widgets) |
| Apps SDK Examples | [developers.openai.com/apps-sdk/build/examples](https://developers.openai.com/apps-sdk/build/examples) |
| Apps SDK examples repo | [github.com/openai/openai-apps-sdk-examples](https://github.com/openai/openai-apps-sdk-examples) |
| Apps SDK UI guidelines | [developers.openai.com/apps-sdk/concepts/ui-guidelines](https://developers.openai.com/apps-sdk/concepts/ui-guidelines) |
| Voice agents (Realtime) | [openai.github.io/openai-agents-js/guides/voice-agents/quickstart](https://openai.github.io/openai-agents-js/guides/voice-agents/quickstart) |
| SnapDish voice API | Backend `POST /v1/voice` — see [backend/README.md](../backend/README.md) |

---

## Summary

- **Yes, there are templates** so you can code as little as possible on the front end.
- **Chatbot:** Use **ChatKit Starter App** (your app) or **Apps SDK Pizzaz** (inside ChatGPT).
- **Maps:** Pizzaz has a map view; with ChatKit, embed a map in a Card/Box or use list + “Open in Maps”.
- **Ecommerce/widgets:** ChatKit **Card**, **ListView**, **Button**, **Badge**, etc.; Pizzaz has **checkout**, list, carousel. Use the **Widget Builder** and **UI Kit**.
- **Video:** Add a button that captures/selects video and uploads (templates support file/attachment flows).
- **Voice:** Add a **voice button** and wire it to SnapDish `POST /v1/voice` or the Realtime API; not included in the chat templates.

Using these templates gives you the chatbot and most widgets out of the box; you only add map (if needed), video capture/upload, and voice button.

---

## Mobile UI templates (iOS / Android — better than Material UI)

For the **SnapDish mobile app** (Expo / React Native), use a **mobile-first UI library** rather than a web-oriented one like Material UI. These are better suited for native iOS/Android look and chat/camera/voice UIs:

| Library | Best for | Notes |
|---------|----------|--------|
| **Tamagui** | Native-feel, performance, one codebase (mobile + web) | Composable components, themes, optimizing compiler. Not Material; works with Expo. [tamagui.dev](https://tamagui.dev) · [Expo guide](https://tamagui.dev/docs/guides/expo). **Recommended** for a custom, polished mobile look. |
| **NativeUI** (allshadcn) | Platform-native look (iOS HIG + Android Material) | Copy-paste components; native-style animations, haptics, bottom sheets. [allshadcn.com/components/nativeui](https://allshadcn.com/components/nativeui). |
| **React Native Paper** | Material Design 3 on mobile | Material 3 components; consistent, accessible. Use if you want Material on both platforms. [callstack.github.io/react-native-paper](https://callstack.github.io/react-native-paper). |
| **Gluestack-ui** | Theming and forms | Customizable primitives; works with Expo. [gluestack.io](https://gluestack.io). |

**Recommendation:** Prefer **Tamagui** or **NativeUI** for an app that should feel native and not “web Material.” The SnapDish app in `mobile/` can be scaffolded with any of the above; switch by swapping the provider and components.

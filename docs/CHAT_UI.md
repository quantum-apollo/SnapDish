# Chat UI — Nearby restaurant listings (enriched discovery)

**SnapDish is a mobile-first application** (native or hybrid), not a web-first product. To minimize custom front-end code, use OpenAI’s templates (ChatKit Starter App or Apps SDK Pizzaz); see **[FRONTEND_TEMPLATES.md](FRONTEND_TEMPLATES.md)** for maps, chatbot, ecommerce widgets, and voice/video buttons. The chat UI should be designed for phones first: single-column layout, touch-friendly targets, safe areas (notch, home indicator), then adapt for larger screens if needed.

SnapDish should show **nearby restaurant listings inside the chat** in a rich, card-based layout with **rounded corners** and the **chat input fixed at the bottom** — similar to the “fullscreen mode for enriched discovery” pattern from [What makes a great ChatGPT app](https://developers.openai.com/blog/what-makes-a-great-chatgpt-app).

## Target experience (mobile-first)

- **Context:** User asks for nearby restaurants (or places to eat). Chef Marco (or your backend) returns structured results (e.g. from Search agent, places API, or `nearby_stores` extended to restaurants).
- **In the chat:** Instead of only plain text, the UI shows an **enriched discovery block**:
  - A scrollable area with **restaurant cards** (rounded corners, image, name, address, distance, optional rating/cuisine).
  - Same conversation thread above it; **chat input stays at the bottom** (above safe area / home indicator).
- **Visual reference:** The blog’s find-homes fullscreen example: card list, clean spacing, rounded corners, message area + input at bottom — interpreted for **mobile** (single column, thumb-friendly).

So: **listings live inside the chat**, in a dedicated “Show” block (see Know/Do/Show in the blog), not on a separate screen.

## Layout (high level)

```
┌─────────────────────────────────────────┐
│  Chat header / thread title (optional)  │
├─────────────────────────────────────────┤
│                                         │
│  [ Assistant message (text) ]           │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Enriched discovery (rounded)    │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐        │   │
│  │  │Card │ │Card │ │Card │  …     │   │
│  │  └─────┘ └─────┘ └─────┘        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  [ User message ]                      │
│                                         │
├─────────────────────────────────────────┤
│  [ Chat input field ]                   │  ← Fixed at bottom
└─────────────────────────────────────────┘
```

- **Mobile-first:** Single-column layout; full-width discovery block on phone; cards stack vertically or horizontal scroll (e.g. carousel) depending on your framework.
- **Rounded corners:** Rounded container for the discovery block and rounded cards inside to match the blog’s look.
- **Touch targets:** Buttons and tappable cards at least 44×44 pt/dp; adequate spacing between cards.
- **Safe areas:** Respect `safe-area-inset-bottom` (and top/sides if needed) so the input and content clear the home indicator and notch.
- **Chat at bottom:** Input is fixed at the bottom (above safe area); messages and discovery block scroll above it.

## Data shape (for frontend)

When the backend returns “nearby restaurants” (or stores), it should include a **structured list** the frontend can render as cards. Example (align with your API or extend `StoreSuggestion`):

```json
{
  "nearby_restaurants": [
    {
      "id": "place_1",
      "name": "Trattoria Roma",
      "address": "123 Main St",
      "distance_km": 0.5,
      "rating": 4.5,
      "cuisine": "Italian",
      "image_url": "https://..."
    }
  ]
}
```

- **Analyze response:** Today `AnalyzeResponse` has `nearby_stores` (name, address, distance_km). You can reuse that for “stores” or add a separate `nearby_restaurants` (or a generic `nearby_places`) with optional `image_url`, `rating`, `cuisine` for the cards.
- **Voice/agents:** When the Search or Knowledge agent returns place data, the client can show the same card block if the response includes this structure (e.g. via a dedicated “places” block in the response or a follow-up payload).

## Implementation (mobile app)

- **Native (iOS/Android) or hybrid (e.g. React Native, Flutter):** Build a chat screen that (a) renders assistant messages, (b) detects a “nearby_restaurants” (or similar) block in the API response, (c) renders the **enriched discovery** block (rounded cards) inside the message list, (d) keeps the input fixed at the bottom with safe-area insets.
- **Layout:** One scrollable list (e.g. `FlatList` / `ListView` / `LazyColumn`) containing message bubbles and, when present, a discovery block (rounded container with a horizontal scroll or vertical list of cards). Input bar fixed below, padding bottom = safe area.
- **Reference:** **examples/chat-ui/** is a **mobile-first** HTML/CSS mock (narrow viewport, touch targets, safe areas) to translate into your native or hybrid UI. It is not the production app.

## Reference

- **Blog:** [What makes a great ChatGPT app](https://developers.openai.com/blog/what-makes-a-great-chatgpt-app) — “Fullscreen mode for enriched discovery” and “Show” (better ways to present information in the chat).
- **Example in repo:** `examples/chat-ui/` — mobile-first HTML/CSS reference (narrow viewport, touch targets, safe areas, rounded cards, input at bottom) to translate into your **native or hybrid mobile app**.

## Checklist (mobile frontend)

- [ ] **Mobile-first:** Layout and components designed for phone viewport first; tablet/large screen optional.
- [ ] Chat: one scrollable message list + input bar fixed at bottom with **safe-area-inset-bottom**.
- [ ] Enriched block: rounded container, padding; full width on phone (or constrained per your design).
- [ ] Restaurant cards: rounded corners; **min touch target ~44×44 pt/dp**; image, name, address, distance, optional rating/cuisine.
- [ ] Backend: analyze/voice/agents return a structured list (e.g. `nearby_stores` or `nearby_restaurants`) when relevant so the app can render the block.

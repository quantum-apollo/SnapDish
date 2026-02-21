# Chat UI example — Mobile-first, nearby restaurant listings

**SnapDish is a mobile-first application.** This folder is a **reference mock** (HTML/CSS) for the chat screen you will build in your **native or hybrid mobile app** (e.g. React Native, Flutter, SwiftUI, Kotlin). It is not the production UI.

Minimal reference: **enriched discovery** — restaurant cards with **rounded corners**, **chat input at the bottom**, **safe areas** and **touch-sized targets**, similar to the [“Fullscreen mode for enriched discovery”](https://developers.openai.com/blog/what-makes-a-great-chatgpt-app) pattern.

## What’s in this folder

- **index.html** — One assistant message with a discovery block (restaurant cards) and a user message; input at bottom. Viewport and meta set for mobile.
- **styles.css** — **Mobile-first:** single-column cards, full-width layout, 44px min touch targets, `safe-area-inset` for bottom (and left/right on body). Optional tablet breakpoint at 640px.

## How to run (preview only)

Open `index.html` in a browser and use device emulation (e.g. Chrome DevTools → device toolbar) to view at phone width. Or:

```bash
cd examples/chat-ui
npx serve .
```

## Using this in your mobile app

- **Translate the structure** into your framework: scrollable message list + fixed input bar with bottom safe area; when the API returns `nearby_stores` or `nearby_restaurants`, render a discovery block (rounded container + list of cards).
- **Layout:** One column on phone; cards stack vertically (or use a horizontal scroll/carousel if you prefer). Input bar: min height ~44 pt/dp, padding bottom = safe area inset.
- **Touch:** Buttons and tappable cards at least 44×44 pt/dp. See **docs/CHAT_UI.md** for data shape and checklist.

Design reference: [What makes a great ChatGPT app](https://developers.openai.com/blog/what-makes-a-great-chatgpt-app).

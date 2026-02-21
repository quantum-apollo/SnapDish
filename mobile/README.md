# SnapDish mobile app (iOS & Android)

Like Snapchat, but for food.

Expo (React Native) app — one codebase for iOS and Android.

**Template and icons:** We use **Material UI** (Material Design). On mobile that’s **React Native Paper** + **MaterialCommunityIcons**. No self-made icons — all icons come from the template. See **[TEMPLATE_SOURCE.md](./TEMPLATE_SOURCE.md)** for where to get components and icons.

## Run

```bash
cd mobile
npm install
npx expo start
```

- Press **i** for iOS simulator, **a** for Android emulator, or scan the QR code with **Expo Go** on a device.
- In the app, open **Settings** and set **Backend API URL** to your SnapDish API (e.g. `http://localhost:8000` or your machine’s IP like `http://192.168.1.x:8000` for a physical device).

## What’s included

- **Chat tab** — Text input and Send; calls `POST /v1/analyze` and shows Chef Marco’s cooking guidance.
- **Settings tab** — Backend API URL (persisted).
- **Safe areas** — Input and content respect notches and home indicator (44 pt touch targets where applicable).
- **API client** — `src/api/client.ts`: `analyze()`, `voice()`, base URL from Settings.

## Switching UI template

This app is scaffolded with **React Native Paper** (Material 3) so it runs immediately. For a **more native, mobile-suited** look (not Material), use one of these:

| Option | Use when |
|--------|----------|
| **Tamagui** | You want a custom, polished look and one codebase for web + mobile. [tamagui.dev](https://tamagui.dev) · [Expo guide](https://tamagui.dev/docs/guides/expo). |
| **NativeUI** (allshadcn) | You want platform-native feel (iOS HIG + Android). [allshadcn.com/components/nativeui](https://allshadcn.com/components/nativeui). |
| **Gluestack-ui** | You want strong theming and form primitives. [gluestack.io](https://gluestack.io). |

See **docs/FRONTEND_TEMPLATES.md** (section “Mobile UI templates”) for links and comparison. To switch: replace `PaperProvider` and Paper components in `app/_layout.tsx` and `app/(tabs)/index.tsx` with your chosen library’s provider and components.

## Next steps

- **Add live camera preview** — Replace placeholder with `expo-camera` Camera component (already installed)
- **Add real map view** — Integrate `react-native-maps` in Maps tab (already installed)
- **Add voice** — Record button → `POST /v1/voice` → play response
- **Render nearby restaurants** — Show `nearby_stores` / `nearby_restaurants` as cards in Maps/Feed
- **Add app icon and splash** — Customize `app.json` with your branding

## Docs

- **[TEMPLATE_SOURCE.md](./TEMPLATE_SOURCE.md)** — Which template we use; where to get components and icons (React Native Paper + MaterialCommunityIcons).
- **docs/MOBILE_APP.md** — iOS/Android scope, stack, backend API, checklist.
- **docs/CHAT_UI.md** — Layout, safe areas, touch targets, data shape for cards.
- **backend/README.md** — API endpoints and how to run the backend.

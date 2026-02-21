# SnapDish mobile — template and components

This app uses **Material UI** (Material Design). All components and icons come from this template only. There are **no self-made or custom icons**.

---

## Template we use: Material UI (Material Design)

On **mobile** (React Native), the Material UI template is implemented by:

| What | Library | Purpose |
|------|---------|--------|
| **UI components** | **React Native Paper** (Material Design 3) | Buttons, Cards, Text, TextInput, Avatar, etc. — same design system as Material UI on the web. |
| **Icons** | **MaterialCommunityIcons** (from `@expo/vector-icons`) | Official Material Design Icons. Every icon in the app comes from this set only. |

- **React Native Paper** is the standard Material Design 3 library for React Native (the mobile equivalent of Material UI / MUI on the web). See [React Native Paper](https://callstack.github.io/react-native-paper/).
- **MaterialCommunityIcons** is the icon set that ships with this template. We use **only** these icons — no custom icons, no emojis, no other icon libraries.

---

## Where to get components and icons

### React Native Paper (components)

- **Docs:** https://callstack.github.io/react-native-paper/
- **Components:** Button, Card, TextInput, Avatar, Text, Divider, FAB, Appbar, etc.
- **Theming:** `MD3LightTheme` / `MD3DarkTheme` from `react-native-paper` (see `app/_layout.tsx`).

Use these for all buttons, cards, inputs, and layout. Do not mix in random third‑party button or card libraries.

### Icons (MaterialCommunityIcons)

- **Icon set:** Material Design Icons (MDI)
- **Browse/search icons:** https://pictogrammers.com/library/mdi/
- **In code:** `import { MaterialCommunityIcons } from '@expo/vector-icons';` then e.g. `<MaterialCommunityIcons name="food" size={24} color={color} />`

**Icon names** are lowercase with hyphens (e.g. `food-variant`, `silverware-fork-knife`, `map-marker`, `chef-hat`, `camera`, `account`). Always use names from the [MDI library](https://pictogrammers.com/library/mdi/) — no self-made or custom icons.

---

## What we do *not* use

- **Self-made or custom icons.** Every icon is from MaterialCommunityIcons (the template’s icon set).
- **Emojis** for UI. Use MaterialCommunityIcons instead.
- **Other icon sets** (e.g. FontAwesome, custom PNGs). Only MaterialCommunityIcons.
- **Other UI libraries** mixed with Paper. One template only: Material UI (React Native Paper + MaterialCommunityIcons).

---

## File reference

| File | What it uses from the template |
|------|--------------------------------|
| `app/_layout.tsx` | `PaperProvider`, `MD3LightTheme`, `MD3DarkTheme` (Paper) |
| `app/(tabs)/_layout.tsx` | `MaterialCommunityIcons` for all tab icons |
| `app/(tabs)/feed.tsx` | Paper: Card, Text, Avatar; Icons: magnify, map-marker, heart-outline, comment-outline, share-outline, chef-hat, account, food-variant, silverware-fork-knife, leaf |
| `app/(tabs)/maps.tsx` | Paper: Card, Text; Icons: map, map-outline, map-marker, star, chevron-right, silverware-fork-knife, food-variant, leaf, fish |
| `app/(tabs)/camera.tsx` | Paper: Button, Text; Icons: camera, camera-check, image, video |
| `app/(tabs)/chat.tsx` | Paper: Card, TextInput, IconButton; Icons: chef-hat, camera, send |
| `app/(tabs)/profile.tsx` | Paper: Avatar, Button, TextInput, Card, Divider; Icons: (Avatar.Icon uses Paper’s icon prop, e.g. chef-hat, account); Settings: cog, history, heart, chevron-right |

All of the above icons are from **MaterialCommunityIcons** only.

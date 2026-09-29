# Harvest2Value — CRDA Enterprise Design System (Electric Blue)

Enterprise dark-slate theme with vibrant electric blue as the single primary
accent, for the CRDA Regional Agricultural Dashboard. This supersedes the
earlier emerald "Agritech" and navy "Clinicalism" specs.

Light and dark are both first-class (`next-themes`, `.dark` class on `<html>`).
Every color lives in a CSS variable in `app/globals.css` and is exposed to
Tailwind as a token. **Never hardcode hex in components**; use the tokens.

---

## 1. Color tokens

| Token (Tailwind) | Light | Dark | Use |
|---|---|---|---|
| `app-bg` | `#F9FAFB` | `#0B0F17` | Page canvas |
| `sidebar-surface` | `#FFFFFF` | `#070A0F` | Sidebar (deepest layer) |
| `card-surface` | `#FFFFFF` | `#111827` (alt `#161F30`) | Cards, inputs, menus |
| `card-border` | `#E5E7EB` | `#1F293D` (alt `#2D3748`) | All borders / dividers |
| `accent` | `#0052FF` | `#0052FF` | Buttons, active nav, brand fills (white text on top) |
| `accent-hover` | `#003ECB` | `#003ECB` | Hover for `accent` fills |
| `accent-text` | `#0052FF` | `#5B8DFF` | Accent as text/icons (raw `#0052FF` is < 4.5:1 on dark) |
| `text-primary` | `#0B0F17` | `#F3F4F6` | Headings, values |
| `text-secondary` | `#5B616E` | `#8A919E` | Labels, muted copy |
| `success` | `#05B169` | `#05B169` | Good delta, healthy status |
| `warning` | `#F0AD4E` | `#F0AD4E` | Filling / caution |
| `danger` | `#DF2935` | `#DF2935` | Bad delta, critical status |

Rules
- Primary action = `bg-accent text-white hover:bg-accent-hover`.
- Text on `accent` is always white.
- Status is never color alone: pair with an icon, arrow or label.
- Crop chart series (fixed, theme-independent): Tomatoes `#F87171`, Wheat `#FACC15`,
  Olives `#A3E635`, Citrus `#FB923C` (see `CROP_COLORS` in `types/index.ts`).

## 2. Surfaces
- **Card**: `rounded-2xl border border-card-border bg-card-surface p-5` (flat, no blur).
- Interactive hover: `hover:border-accent/50 transition-colors`.
- Focus (every interactive element): `outline-none focus-visible:ring-2 focus-visible:ring-accent`.
- Numerics: `font-mono tabular-nums`. Body font: Plus Jakarta Sans.

## 3. Global layout rules
- **Theme toggle**: fixed **top-right** on every page and layout (mounted once in
  `app/layout.tsx`, `fixed right-4 top-4 z-40`). Page headers reserve `pr-14`
  so nothing sits underneath it.
- **Collapsible sidebar** (dashboard shell): `w-64` expanded, `w-[72px]`
  icon-only when collapsed; toggle button `←` / `→` (`aria-expanded`); collapsed
  items keep an `aria-label` and `title` tooltip. In normal flow (`sticky top-0 h-screen`)
  so content reflows automatically. Hidden below `lg` (mobile drawer is a follow-up).
- **Header**: search, Delegation selector (Mornag / Tebourba / Kelibia), date
  range, delegation weather widget (e.g. `24°C Sunny • Mornag`).

## 4. Routes & user journey
```
/                 Landing hero → "Get Started / CRDA Portal →"
/auth/login       CRDA Agent credentials (Email, Delegation ID, Agent Code)
/auth/2fa         Simulated 6-digit email code → /dashboard
/dashboard        KPIs, weather, quick-add farmer, multi-crop summary
/farmers          Farmer table + CRDAFarmerInput modal + Δ badges
/storage          Silo / cold-storage monitoring
/analytics        Δ Income & Δ Waste trend charts
/ai-assistant     Chat history panel + Groq Llama-3 chat + prompt chips
/settings         Delegation config & account preferences
/support          FAQ, documentation, contact
```
Sidebar nav: Dashboard, Farmers, Storage Facilities, Analytics, AI Assistant,
Settings, Help & Support, Log Out (clears auth state → `/`).

## 5. Delta badges
- Income ↑ good (`success`), ↓ bad (`danger`). Waste ↓ good, ↑ bad.
- Arrow shows direction, color shows good/bad; neutral/no data uses `text-secondary` with "—".

## 6. Implementation rules
- Colocate component prop types; shared domain types in `types/index.ts`.
- Accessible: 4.5:1 text contrast, labelled inputs, `aria-label` on icon-only buttons.
- Domain mocks in `types/index.ts`; API types in `app/lib/api.ts` (mirrors backend).

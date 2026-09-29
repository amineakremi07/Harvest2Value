# Harvest2Value — CRDA Enterprise Design System (Electric Blue)

Enterprise dark-slate theme with electric blue as the single primary accent,
for the CRDA Regional Agricultural Dashboard. Light and dark are both
first-class (`next-themes`, `.dark` class on `<html>`). Every color lives in a
CSS variable in `app/globals.css` and is exposed to Tailwind as a token.
**Never hardcode hex in components**; use the tokens. The one deliberate
exception is the always-dark Optimization Hero (§4.5).

---

## 1. Color tokens

| Token (Tailwind) | Light | Dark | Use |
|---|---|---|---|
| `app-bg` | `#F9FAFB` | `#0B0F17` | Page canvas (dark slate, never pure black) |
| `sidebar-surface` | `#FFFFFF` | `#070A0F` | Sidebar (deepest layer) |
| `card-surface` | `#FFFFFF` | `#111827` (alt `#161F30`) | Cards, inputs, menus |
| `card-border` | `#E5E7EB` | `#1F293D` (alt `#2D3748`) | Borders and dividers |
| `accent` | `#0052FF` | `#0052FF` | Buttons, active states, brand fills (white text on top) |
| `accent-hover` | `#003ECB` | `#003ECB` | Hover for `accent` fills |
| `accent-text` | `#0052FF` | `#5B8DFF` | Accent as text/icons (`#0052FF` fails 4.5:1 on dark slate) |
| `text-primary` | `#0B0F17` | `#F3F4F6` | Headings, values |
| `text-secondary` | `#5B616E` | `#8A919E` | Labels, muted copy |
| `success` | `#05B169` | `#05B169` | Good delta, healthy status |
| `warning` | `#F0AD4E` | `#F0AD4E` | Filling / caution |
| `danger` | `#DF2935` | `#DF2935` | Bad delta, critical status |

Rules
- Primary action: `bg-accent text-white hover:bg-accent-hover`. Text on `accent` is always white.
- Accent-colored text or icons use `text-accent-text`, never `text-accent`.
- Status is never color alone: pair with an icon, arrow or label.
- Crop chart series are fixed and theme-independent: Tomatoes `#F87171`, Wheat `#FACC15`,
  Olives `#A3E635`, Citrus `#FB923C` (`CROP_COLORS` in `types/index.ts`).

## 2. Surfaces & interaction
- **Card**: `rounded-2xl border border-card-border bg-card-surface p-5` (`glassCard` in
  `components/styles.ts`; flat, no blur).
- Hover on interactive surfaces: `hover:border-accent/50`.
- Focus on every interactive element: `outline-none focus-visible:ring-2 focus-visible:ring-accent`.
- Numerics: `font-mono tabular-nums`. Body font: Plus Jakarta Sans.
- Dialogs use native `<dialog>` (`components/Modal.tsx`), variants `modal` and right-hand `drawer`.

## 3. Routes & user journey
```
/                 Hero landing → "Access CRDA Portal →"
/auth/login       Agent credentials: Email, Delegation ID, Agent Code
/auth/2fa         6-digit email code → /dashboard
/dashboard        KPIs, Optimization Hero, crop donut, storage risk, farmer overview
/farmers          Farmer table, add/edit modal, row analytics expander, analytics drawer
/storage          Silo / cold-storage / warehouse monitoring
/analytics        Δ Income & Δ Waste trends, regional comparison
/ai-assistant     Chat history panel + Groq Llama-3 chat + prompt chips
/optimization     Regional plan (4-step flow) and Buyer allocation (solver) tabs
/settings         Delegation preferences, account
/support          FAQ, documentation, contact
```
Signed-out visitors to any dashboard route are redirected to `/auth/login`.

## 4. Layout architecture

### 4.1 Global
- **Theme toggle**: fixed top-right on every page (mounted once in `app/layout.tsx`,
  `fixed right-4 top-4 z-40`). Page headers reserve `pr-14`.

### 4.2 Hero landing (`/`)
Centered hero: eyebrow pill, H1 "Harvest2Value — Enterprise Regional Agricultural
Optimization", subtitle, solid-blue CTA to `/auth/login`, then three value cards
(Waste Reduction, Storage Optimization, Farmer Analytics).

### 4.3 Auth & 2FA (`/auth/*`)
Centered card (`AuthShell`) under the brand. Login: three labelled fields, inline
`role="alert"` errors. 2FA: six single-digit inputs with auto-advance, backspace,
arrow keys and paste; submits automatically when complete. Both state that the
flow is a demo (no real verification).

### 4.4 Dashboard shell (`(dashboard)` route group)
- **Collapsible sidebar**: `w-64` expanded, `w-[72px]` icon-only. Toggle `←`/`→`
  (`aria-expanded`); collapsed items keep `aria-label` and `title`. Sticky, in
  normal flow so content reflows. Links: Dashboard, Farmers, Storage Facilities,
  Analytics, AI Assistant, Settings, Help & Support, and Log Out (clears auth →
  `/`). Hidden below `lg` (mobile drawer is a follow-up).
- **Header**: brand, search, weather chip (e.g. `24°C Sunny • Mornag`),
  **Delegation selector** (Mornag / Tebourba / Kelibia, global context) and date range.

### 4.5 Dashboard Optimization Hero
Flagship callout directly under the KPI cards. Always dark slate (`#0B0F17`) with
an electric-blue border and soft glow, in both themes. Contents: badge
"Core engine • Groq / AI solver ready", heading "Run Regional Storage & Spoilage
Optimization", subtitle naming the delegations, primary "Launch Optimization
Engine →" (`/optimization`), secondary "View Active Plan" (`/optimization#latest-plan`),
and a status strip (`x% spoilage → potential y% waste reduction (~z kg saved)`)
that shows the last run when one exists, else a live preview.

### 4.6 Farmer analytics
- **Row expander** (`/farmers`): an "Analytics" toggle per row (`aria-expanded`)
  opens an inline panel with waste change (kg), income change (TND), crop
  breakdown bar, storage & risk (recommended facility, fill level), plus
  "Full analytics" and "Quick edit".
- **Analytics drawer**: right-hand drawer with recommendation card, individual
  crop donut, quarter-over-quarter income/waste bars, and storage allocation.
- **Delta badges**: income ↑ good, waste ↓ good; arrow = direction, color =
  good/bad; no data shows "—".

### 4.7 Optimization page
Tabs: **Regional plan** (stepper: Input summary → Execution → Before vs after →
Reallocation plan; results anchored at `#latest-plan`) and **Buyer allocation
(solver)** (the original buyer/storage optimizer, charts and What-If chat).

## 5. Implementation rules
- Colocate component prop types; shared domain types in `types/index.ts`.
- Accessible: 4.5:1 text contrast, labelled inputs, `aria-label` on icon-only buttons.
- Anything sample or estimated is labelled as such in the UI.

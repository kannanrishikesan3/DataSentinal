# Design

Visual system for the DataSentinel dashboard. Product register — see PRODUCT.md
for the strategic brief this implements (Datadog/Grafana-adjacent, restrained,
"vigilant/precise/unflashy").

## Tokens

All tokens live in `frontend/src/index.css` as CSS custom properties, defined
in OKLCH, on `:root` for light and re-declared under
`@media (prefers-color-scheme: dark)` for dark — there is no manual theme
toggle, so both palettes are first-class. Tailwind v4's `@theme inline` block
maps every token to a utility class (`bg-background`, `text-primary`,
`border-border`, etc.). **Never hardcode a Tailwind color utility
(`slate-500`, `red-600`, a hex value) in a component — always use a semantic
token.**

### Core tokens

| Token | Role |
|---|---|
| `background` / `foreground` | Page background and default text |
| `card` / `card-foreground` | Elevated surfaces (Card, Dialog content) |
| `popover` / `popover-foreground` | Dialogs, dropdowns, tooltips |
| `primary` / `primary-foreground` | Primary actions, links, active nav state, focus rings, chart accent |
| `secondary` / `secondary-foreground` | Secondary buttons, neutral badges |
| `muted` / `muted-foreground` | De-emphasized text, skeletons, subtle backgrounds |
| `accent` / `accent-foreground` | Hover/selected states on menu items, selects |
| `destructive` / `destructive-foreground` | Destructive actions, error text |
| `border` / `input` / `ring` | Borders, form control borders, focus ring |
| `success` / `success-bg` / `success-fg` | Positive status (completed scans, active tokens, toasts) |

### Sidebar tokens (persistent dark nav rail, both color schemes)

`sidebar`, `sidebar-foreground`, `sidebar-border`, `sidebar-accent`,
`sidebar-accent-foreground`, `sidebar-muted-foreground` — the sidebar and the
login page's background use these; they stay dark even in light mode
(Datadog/Grafana reference), which is the one deliberate "second neutral
layer" per product.md's guidance, not a bug.

### Severity tokens

`severity-{critical,high,medium,low,info}` each have three variants:
- `severity-X` — solid, for dots and chart fills/strokes (`SEVERITY_CHART_COLORS`
  in `severity-badge.tsx` exports these as `var(--severity-x)` strings, live
  across a theme change, not resolved-once hex).
- `severity-X-bg` — soft tint background, for badges.
- `severity-X-fg` — text color paired with `-bg`, AA contrast in both schemes.

Hues are deliberately distinct from `primary`'s 258° so "this is clickable"
is never visually confused with "this is a risk signal": critical=25°
(red), high=45-50°, medium=85-90°, low=220° (cyan, not primary's indigo),
info=255° at ~0 chroma (neutral gray). Reuse these for anything
severity-*equivalent* too (e.g. Endpoints page's risk-score band), not a
second color table.

Non-severity workflow states (scan status, enrollment token status) reuse
`success` / `destructive` / `muted` / `accent` / `severity-medium` as
appropriate — see `STATUS_VARIANT` in `scans.tsx` and `STATUS_STYLES` in
`enrollment-tokens-section.tsx` for the exact mapping.

### Radius

`--radius: 0.5rem`, mapped to `rounded-sm/md/lg/xl` via `@theme inline`.
Moderate, not pill-shaped — matches the "precise, unflashy" personality.

## Typography

System font stack (no imported font) — Tailwind's default sans. One family
throughout, per product.md's "product UIs don't need display/body pairing."
Headings are `text-xl font-semibold tracking-tight`; body/table text is
`text-sm`; secondary/meta text is `text-xs text-muted-foreground`.

## Color strategy

Restrained: tinted cool neutrals (hue 255, chroma 0.002-0.02) + one indigo
accent (`primary`, hue 258) used only for actions, links, focus, current
selection, and as the single chart accent for non-severity data. Severity
badges/charts are the one place a fuller palette is deliberately used
(5 hues), because severity *is* the primary signal (Design Principle #2 in
PRODUCT.md) — everywhere else stays restrained.

## Components

Every shared primitive (`frontend/src/components/ui/`) is token-driven with
no per-usage color overrides needed for light/dark — `Button`, `Card`,
`Dialog`, `Input`, `Label`, `Select`, `Table`, `Badge`, `Toast`. Dialogs/
selects/toasts animate via `tw-animate-css` (150-250ms, `fade-in`/`zoom-in-95`/
`slide-in-from-bottom-2`), matching product.md's motion guidance — state
transitions only, nothing decorative.

## Motion

`prefers-reduced-motion: reduce` is honored globally (`index.css`) —
animation/transition durations collapse to ~0 rather than being disabled
per-component.

## Regenerating

Re-run `/impeccable document` after significant visual changes to refresh
this file from the actual code, rather than hand-editing it out of sync.

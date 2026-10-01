# AI Call Agent — Design system

## Direction

Use the supplied Attio reference as the visual baseline: an editorial, precise interface on a near-white canvas, graphite typography, hairline borders, and cobalt as the single brand accent. Airtable is a secondary workflow reference for readable CRM tables and clear inline actions. This is an operator CRM, so preserve compact table and queue density instead of copying marketing-page whitespace.

The attached reference itself says its measurements are normalized interpretations and component examples are reconstructions. Treat its values as a design direction rather than exact source specifications.

## Foundations

- Canvas: `#ffffff`; alternate surface: `#f4f5f6`; inset surface: `#f8f9fa`.
- Main text: `#1c1d1f`; secondary text: `#505967`; tertiary text: `#626a75`. These muted values are intentionally darker than the supplied Attio measurements to keep small UI labels above WCAG AA contrast on white and paper surfaces.
- Borders: `#e4e7ec` with a lighter divider `#eef0f2`.
- Accent: `#266df0`; use for focus, links, active states, and the primary action only.
- Semantic status colors are permitted only for status communication, never as extra brand accents.
- UI type: Inter, weight 500 as the default, with a system fallback and slightly tight tracking.
- Base spacing: 4px; common increments 8, 12, 16, 20, 24, 32px.
- Inputs and buttons: 10px radius. Badges: 7px. Cards: 11–14px.
- Content width: 1440px. Sidebar is persistent at desktop widths and becomes a compact navigation control on small screens.
- Shadows stay subtle and cool: blue-tinted, low-opacity, with borders doing most of the separation.

## Component behavior

- Buttons: 40px minimum height; near-black filled primary, outlined secondary, transparent ghost, explicit danger treatment.
- Inputs: white surface, visible label, clear placeholder, cobalt focus ring, inline validation and disabled states.
- Navigation: monochrome line icons, quiet hover, clear active route, keyboard focus, Russian labels.
- Tables: compact rows with persistent headers where helpful, readable date and status values, responsive overflow or stacked cards on narrow screens.
- Statuses: localized labels with semantic, low-saturation backgrounds. Unknown values receive a safe neutral label.
- Feedback: loading, empty, error, and success states use the same page vocabulary and offer a sensible next step.
- Dialogs and destructive or high-impact actions must be keyboard accessible and clearly described.

## Theme

Light is the default. Dark mode uses the same roles and contrast hierarchy with near-black canvas, graphite surfaces, light text, quiet borders, and the same cobalt accent. Store the user's choice and expose a keyboard-accessible theme toggle.

## Motion and accessibility

- Motion provides feedback or continuity only; keep transitions short (120–180ms) and honor `prefers-reduced-motion`.
- Focus indicators must remain visible. Icon-only controls need accessible names.
- Keep semantic headings, table headers, form labels, button names, and useful live feedback.
- Do not encode status by color alone.

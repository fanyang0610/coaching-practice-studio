# Inferred Design System: Erickson Coaching International

This brief is inferred from the public Erickson Coaching International site at `https://www.erickson.edu/` after the resolved `awesome-design-md` candidate returned 404. Use it as a local design contract for the app, not as a claim of ownership over Erickson brand assets.

## Visual Theme

- Professional coach-training institution, not a playful chat app.
- Bright white and soft blue canvas with confident institutional blue CTAs.
- Uppercase section labels and concise, high-contrast hierarchy.
- Calm, airy, and credible; avoid neon, heavy gradients, and decorative clutter.

## Color Roles

- Canvas: `#f7fbff`
- Surface: `#ffffff`
- Soft blue surface: `#edf6fb`
- Primary text: `#102f47`
- Secondary text: `#5d7486`
- Erickson blue: `#126fa8`
- Deep blue: `#0d4e7a`
- Border: `#d7e7f1`
- Warm accent: `#f4b44d`

## Typography

- Use `Noto Sans SC`, `Manrope`, and system sans-serif fallbacks.
- Headings: bold, compact, institutional.
- Eyebrows: uppercase English with moderate tracking.
- Body: readable 14-16px; avoid oversized hero type inside the tool.

## Components

- Primary actions: solid Erickson blue, rectangular with small radius.
- Secondary actions: white or pale blue with blue border and text.
- Module switching: compact segmented tabs, not tall cards on mobile.
- Tracker: blue rail with numbered steps, all steps visible on phone.
- Chat: white surface, calm message bubbles, strong internal scrolling.
- Settings: collapsible utility drawer/overlay, not permanent vertical mass.

## Layout

- The product is a tool and must fit in one viewport.
- Outer document should not scroll; chat history scrolls internally.
- Laptop target: full usable layout at `1440x900`.
- Phone target: full usable layout at `390x844`.
- Keep module switcher, tracker, chat, composer, mic/send, skip/reset visible.

## Responsive Rules

- At phone width, reduce vertical chrome before reducing readability.
- Prefer compact controls, one-line tabs, and short tracker copy.
- Use `minmax(0, 1fr)` and `box-sizing: border-box` to prevent overflow.
- No horizontal scroll at any supported viewport.

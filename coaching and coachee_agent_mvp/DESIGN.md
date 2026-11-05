# Design System: Coaching Practice Studio

## Source and Intent

This design brief is adapted for Coaching Practice Studio after reviewing the `awesome-design-md` pattern and borrowing the spirit of calm editorial minimalism from workspace tools such as Notion and conversational clarity from Intercom. It is not meant to imitate another brand one-to-one. It defines how Coaching Practice Studio should feel: calm, credible, reflective, and quietly supportive.

The product is a coaching practice environment, not a sales dashboard. Every visual choice should reduce pressure, keep attention on the conversation, and help the user think clearly.

## 1. Visual Theme & Atmosphere

Coaching Practice Studio should feel like a well-lit coaching studio translated into software:

- Airy, soft, and structured rather than dense or flashy
- Trustworthy and calm rather than hyper-technical
- Warmly professional rather than clinical
- Focused on conversation flow, progress, and reflection

The visual core is a cool paper-blue canvas with white cards, a steady coaching blue for interactive emphasis, and a restrained warm gold accent for highlights. Decorative effects should stay subtle and supportive. The interface may use gentle gradients, soft radial glows, and light geometric texture, but never loud neon effects, glossy glassmorphism, or heavy ornamental illustration.

## 2. Color Palette & Roles

### Primary foundation

- **Studio Background**: `#f3f8fd`
  Use for the page canvas and large background areas.
- **Paper White**: `#ffffff`
  Use for cards, message bubbles, sheets, and input surfaces.
- **Paper Mist**: `#f8fbff`
  Use for soft section fills and elevated interior surfaces.
- **Surface Blue Tint**: `#eef5fb`
  Use for secondary surfaces, subtle selected states, and user-side message fills.

### Text and structure

- **Ink**: `#18364a`
  Primary text, headings, core UI labels.
- **Ink Strong**: `#183f5a`
  Slightly brighter headline or emphasized control text.
- **Muted Slate**: `#62809a`
  Secondary copy, helper text, instructional labels.
- **Border Mist**: `#d8e5f2`
  Standard borders and dividers.

### Interactive colors

- **Coach Blue**: `#1979ba`
  Primary buttons, active states, focus moments, selected controls.
- **Coach Blue Hover**: `#0f6aa8`
  Hover and active darkening for primary controls.
- **Deep Session Blue**: `#115488`
  Used in tracker bars, strong progress surfaces, and high-emphasis panels.
- **Session Blue Bright**: `#2389cb`
  Used for gradients or lively but still calm action emphasis.

### Warm accent

- **Reflection Gold**: `#f0b95a`
  Use sparingly for highlights, subtle glow accents, or stage emphasis.
- **Warm Apricot Tint**: `rgba(245, 188, 120, 0.24)`
  Decorative background bloom only, never core text or button color.

### Usage rules

- Blue is the main action color.
- Gold is a supporting accent, not a second brand primary.
- Keep contrast high for text-heavy areas.
- Avoid introducing purple, harsh green, or bright red as broad thematic colors.

## 3. Typography Rules

### Font families

- **Primary Latin UI font**: `Manrope` when installed, otherwise the system UI font (San Francisco / Helvetica Neue, Segoe UI, Roboto)
- **Primary CJK font**: the system Chinese font (PingFang SC, Microsoft YaHei, Noto Sans SC)
- **No web-font downloads**: a large share of learners is in mainland China, where Google Fonts is blocked and stalls page loads. Use locally installed fonts only.
- **Fallbacks**: `system-ui`, `sans-serif`

The app is bilingual and must feel coherent in both English and Chinese. Typography should remain clean and legible first, expressive second.

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|--------|-------------|----------------|-------|
| Hero / Major heading | 30-40px | 800 | 1.05-1.15 | -0.02em | Reserved for top-level screens only |
| Section heading | 22-28px | 800 | 1.15-1.2 | -0.01em | Use for tracker and major panels |
| Card title | 18-20px | 700-800 | 1.2 | -0.01em | Module cards, prominent labels |
| Primary body | 16px | 400-500 | 1.5-1.6 | normal | Default reading size |
| Supporting body | 14px | 400-500 | 1.45-1.55 | normal | Hints, secondary notes |
| Eyebrow / metadata | 11-12px | 700-800 | 1.2-1.35 | 0.08em-0.12em | Uppercase in English only |
| Button label | 15-16px | 700-800 | 1.2-1.35 | normal | Clear and direct |

### Typography principles

- Use strong weight rather than oversized type to create emphasis.
- Tighten tracking slightly on larger headings, but do not over-compress.
- Keep paragraph width moderate and readable.
- Chinese text should not be forced into aggressive negative tracking.
- Avoid decorative serif pairings unless the user explicitly wants a more editorial redesign.

## 4. Component Stylings

### Module cards

- Large, welcoming, and touch-friendly
- Rounded corners in the 18-26px range
- Soft layered backgrounds with restrained gradient or pattern detail
- Clear selected state using deeper blue, brighter contrast, and stronger shadow
- Must work as two-up cards on desktop and still feel balanced on iPhone widths

### Tracker / stage progress

- Should feel like a confident guidance rail, not a gamified badge strip
- Prefer deep blue surfaces with white text
- Progress dots can be more graphic and structured than the rest of the UI
- Active state should feel precise and reassuring

### Chat surfaces

- Assistant messages: white or near-white with quiet borders
- User messages: light blue-tinted surface
- Message bubbles should be comfortable and friendly, never comic or oversized
- Preserve a clear left/right distinction without turning the layout into a loud messenger aesthetic

### Composer and actions

- Input area should feel stable and anchored
- Primary send action should be visually obvious
- Secondary actions should remain quiet but easy to find
- Voice input can use a slightly more tactile visual language than other secondary actions

### Settings sheet

- Read as a gentle utility drawer, not a modal trap
- White surface, soft border, subtle blur acceptable
- Controls should look practical and clear, not overly stylized

## 5. Layout Principles

### Overall structure

- Prioritize a single focused conversation column
- Keep max content width around `980px`
- Use vertical stacking and soft containment rather than dense multi-panel dashboards
- Preserve the “one page” mobile experience where the chat and controls remain easy to use without chaotic scrolling

### Spacing scale

- Base rhythm: `8px`
- Common steps: `8, 10, 12, 14, 16, 18, 20, 24, 28, 32`

### Radius scale

- Small controls: `14-18px`
- Cards and sheets: `18-22px`
- Emphasis cards: `24-26px`
- Pills / dots: `999px`

### Density rules

- Favor breathing room over compression
- Avoid long walls of helper text
- Keep critical controls visually grouped
- Use layout to create calm sequencing: choose module, check stage, converse, then advance/reset

## 6. Depth & Elevation

Use depth softly and consistently.

### Elevation tiers

- **Base**: no shadow, used for page-level background
- **Card**: `0 16px 36px rgba(17, 73, 119, 0.10)`
- **Interactive hover**: slightly stronger than card, with minimal lift
- **Active emphasis**: up to `0 24px 42px rgba(17, 73, 119, 0.20)` for selected module cards or key highlighted surfaces

### Depth principles

- Prefer soft shadows over hard outlines
- Borders should stay light and cool
- Decorative glows must remain subtle and never reduce readability
- Avoid dark-mode style contrast tricks on light surfaces

## 7. Do's and Don'ts

### Do

- Keep the interface calm, bright, and supportive
- Preserve the blue-white-gold palette
- Make buttons and cards feel comfortably touchable
- Use subtle geometric decoration when it helps the UI feel crafted
- Keep conversation readability more important than visual spectacle
- Design every UI adjustment for both desktop and iPhone-sized screens
- Favor emotionally steady language in labels and microcopy

### Don't

- Don’t turn the app into a generic enterprise dashboard
- Don’t introduce purple-heavy gradients or neon effects
- Don’t use heavy glassmorphism, thick black borders, or harsh shadows
- Don’t make the coaching UI feel childish, playful, or gamified
- Don’t crowd the bottom composer on mobile
- Don’t hide key actions behind ambiguous icon-only controls when text would be clearer

## 8. Responsive Behavior

### Target breakpoints

- **Desktop**: `1024px+`
- **Tablet / small laptop**: `768px-1023px`
- **Phone**: `767px and below`
- **Small phone focus zone**: around `390px` wide

### Mobile rules

- Primary actions must remain reachable in the thumb zone
- Module cards should remain two-up when they still fit clearly; otherwise reduce visual complexity before changing the information architecture
- Reduce height before reducing clarity
- Keep text at or above readable mobile sizes
- Respect safe-area insets
- The composer, tracker, and message area must feel like one coherent flow, not stacked unrelated boxes

### Mobile browser guardrails

Every UI/UX change must preserve the phone browser contract:

- Work with the actual Gradio DOM structure first. Prefer direct `Row` children for equal-width controls, and avoid fixing width bugs by piling on fallback selectors.
- Paired controls must fill their row: use two equal tracks such as `repeat(2, minmax(0, 1fr))`, allow children to shrink with `min-width: 0`, and avoid partial-width floating buttons.
- Keep one viewport on phones. The document shell should stay bounded with `100dvh` and safe-area insets; only the chat transcript should scroll internally.
- Verify the sandbox path without opening the normal Chrome profile: run with `STUDIO_INBROWSER=0` and use `manual_ui_probe.py`, which captures with an isolated temporary browser profile.
- Before reporting UI completion, check both `1440x1200` desktop and `390x844` mobile screenshots. The phone view must show module controls, settings, tracker, chat, composer, mic/send, and skip/reset with no horizontal clipping.
- During a conversation the chat should get at least half of a `390x844` screen (about 56% today; 44% on a `375x667` iPhone SE). The compact phone layout keeps every band but shrinks it: one-line mode card (name and allowance), one-row stage bar (stage name plus dots), and a composer with the message box, mic and Send on one row and Skip Ahead / New Session on a slim row below.
- Keep the message box text at 16px on phones. Smaller text makes iPhones zoom the page when the box is tapped.
- Gradio prefixes every custom CSS selector with `.gradio-container… .contain`. Start phone selectors at `#app-shell`; a selector that starts at `body` (e.g. `body main.contain #app-shell`) never matches. Some older rules in `web_assets.py` still have that dead form.

### Desktop rules

- Use width to improve breathing room, not to create unnecessary columns
- Keep the central conversation stage dominant
- Avoid large dead zones on wide screens; use restrained background decoration instead

## 9. Interaction & Motion

- Motion should be brief, calm, and confidence-building
- Hover lift: subtle vertical shift or shadow increase only
- Selected states should feel locked-in and stable, not bouncy
- Avoid springy, playful animations
- Use motion to support orientation and state change, not decoration

## 10. Accessibility & Content Behavior

- Maintain strong text contrast on all light surfaces
- Focus indicators must be clear on buttons, radios, inputs, and custom mic controls
- Touch targets should be comfortable for phone use
- Never rely on color alone to communicate active stage or selection
- Support English and Chinese gracefully in all layouts

## 11. Agent Prompt Guide

When creating or updating UI for Coaching Practice Studio, optimize for:

- Calm coaching atmosphere
- Clear conversation flow
- Friendly but disciplined visual language
- Desktop and iPhone usability equally
- Blue-led palette with restrained warm accent

### Good prompt patterns

- “Design this screen for Coaching Practice Studio using the project `DESIGN.md`: calm studio-blue background, white conversation surfaces, clear coaching hierarchy, and mobile-safe controls.”
- “Keep the interface reflective and professional, not startup-flashy. Prioritize readability, strong primary actions, and a focused chat column.”
- “Use subtle geometric texture and soft depth, but keep the product feeling emotionally steady and uncluttered.”

### Final check before shipping UI work

1. Does it still feel like a coaching environment rather than a dashboard?
2. Is the main conversation path obvious in under three seconds?
3. Does it remain readable and usable around `390px` width?
4. Are blue and gold used with restraint?
5. Would the screen still feel calm after a 15-minute session?

# ECHOTRACE interface — 2026-09-25

## Direction

An audio investigation workspace with smoked navy glass, ice blue actions, restrained spectral illustration and legible evidence. The visual language suggests precision without imitating official NSA branding. The primary user imports a suspicious recording, reviews measured observations and model output, compares derivatives and exports a reproducible record.

The user invoked frontend-design, framer-motion and ui-ux-pro-max. Their instructions and the UI UX design-system/UX search informed this implementation. The existing React web application is preserved; platform-specific React Native guidance does not imply a migration. The dark palette follows the user's explicit request rather than the search tool's light palette suggestion.

## Tokens and composition

- Background `#070c13`; glass navy `#142131`; primary text `#edf3f9`; muted text `#a0afc1`.
- Ice blue `#a6d8ed` for actions, amber `#e9ca91` for caution, coral `#f2a397` for elevated model scores. Color is accompanied by textual labels.
- Locally hosted Outfit for headings, IBM Plex Sans for interface prose, IBM Plex Mono for compact metadata. No runtime Google Fonts requests.
- Floating navigation and header, generous intake panel, crisp data panels and responsive stacked investigation layout.
- Glass uses tint, a subtle specular edge and backdrop blur. SVG displacement affects only decoration; text, plots and controls remain sharp. Opaque fallback for unsupported backdrop filters.

## Supplied components

`src/components/ui/scroll-morph-hero.tsx` adapts the supplied scatter/line/circle concept to nine procedural signal specimens. Native page scrolling and explicit Circle/Align/Scatter buttons change arrangements. It does not intercept wheel/touch scrolling. These specimens are visibly labeled illustrative and never enter analysis results.

`src/components/ui/liquid-glass.tsx` adapts the supplied layered glass concept into reusable GlassEffect, GlassButton and GlassFilter. Unrelated stock photos, external dock links and layout-shifting hover padding were omitted. Intake, evidence, result and batch panels share the surface treatment.

Tailwind v4 is configured through Vite, shadcn-compatible `components.json` and `@/` aliases are present, and `src/lib/utils.ts` provides `cn`. Motion uses the maintained `motion/react` entry point. `redesign.css` is the final visual layer over the original functional layout styles.

## Interaction and accessibility

View changes animate opacity/translation; buttons have restrained spring feedback. Reduced-motion preferences disable decorative transitions and scroll-driven morphing. Manual arrangement controls still work instantly. No score animation manufactures intermediate analytical values.

Visible keyboard focus, a skip link, semantic buttons, live processing status and a keyboard-operable waveform are retained. Major targets are at least 44px. Hidden mobile navigation is removed from keyboard navigation through CSS visibility and Escape closes the open menu. Responsive rules cover 1100px, 800px and 650px layouts; full mobile interaction review remains pending.

## Verified and pending

- TypeScript and production Vite build pass after integration.
- Chrome accessibility inspection confirms the new intake headings, signal arrangement buttons, file picker, history and connected engine render from the live application.
- macOS ScreenCaptureKit failed with error -3811; concurrent user Chrome activity prevented further reliable interaction. Screenshot-based desktop/mobile visual review and complete click-through remain pending, not claimed complete.
- The backend and score semantics are unchanged. The current learned baseline is uncalibrated and has a documented known-synthetic failure; polished design does not establish detection quality.

## Superseding direction: Graphite — 2026-09-25

User rejected the blue palette, display typography, Engine online badge and decorative signal controls. The active application now uses Public Sans, a black/grey palette, neutral glass surfaces with layered highlights and contact shadows, and plain task labels. The original morph component remains unused source; it is no longer part of the interface. Intake is a working upload surface with an explanation of actual capabilities and a recent-recordings list linked to real analyses. No illustration masquerades as evidence.

This direction supersedes the earlier Outfit/ice-blue/signal-study guidance above. Motion is restricted to view transitions and button feedback with reduced-motion support. Scientific data remains sharp. Desktop screenshots of intake and a real result were inspected successfully in this revision; recent-recording navigation passed. Broader responsive/accessibility QA remains listed in the plan.

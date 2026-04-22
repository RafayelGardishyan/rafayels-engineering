# Design System Philosophy

## Visual Identity
- **Dark mode first** — `#0a0e17` base with blue/cyan accent palette
- **Theme toggle** — Manual dark/light toggle in nav, persists to localStorage; OS preference as default
- **Grid background** — Sparse 40px grid (not dense blueprint) with radial top glow for depth
- **Typography triad** — Instrument Serif (display), Schibsted Grotesk (body), DM Mono (code); serif used consistently across hero, section titles, and card headings to create editorial cohesion
- **Gradient accent** — Hero title uses blue→cyan gradient text to differentiate from generic dark sites
- **Multi-color palette** — Pipeline steps, feature icons, and agent badges use distinct palette colors (violet, blue, emerald, orange, cyan, rose) — never monochromatic blue

## Layout Principles
- **Hero height** — 70vh max, never more; hero should feel full but not empty
- **Stats bar** — Concrete numbers (29/22/19/16) provide social proof directly in the hero
- **Card hover accents** — Colored top-border reveals on feature cards tie back to icon colors
- **Pipeline connectors** — Horizontal arrows on desktop, vertical chevrons on mobile (never hidden)
- **Nav always visible** — Nav shows transparent on load, gains background on scroll (never hidden initially)
- **Feature icons 52px** — Large enough to be recognizable at reading distance
- **Pipeline step numbers** — Display-sized colored numerals (not tiny mono text) for strong visual hierarchy

## Interaction
- **Terminal cursors** — Code blocks show blinking cursor to suggest a live terminal
- **Hover reveals** — Pipeline step numbers and commands highlight on hover
- **Scroll animations** — 24px translateY reveals with staggered timing (0.07s intervals)

## Constraints
- Single-file HTML (no build step)
- No external JS dependencies
- All CSS embedded via design tokens
- Accessibility: skip-link, ARIA labels, focus-visible, prefers-reduced-motion, print stylesheet
- **All external links must resolve** — Never ship broken hrefs; link to repo paths (/issues, /releases, #readme) not vanity URLs

# Iteration 1 Changes

Everything looks good. Here's a summary of all the changes I made and the skills applied:

---

## Changes Applied

### /polish — P1: Theme Toggle Initialization Bug
**Fixed** the dark mode toggle so it works on first click. The root cause was that on initial load without a saved preference, neither `theme-light` nor `theme-dark` class was set. Now the JS explicitly detects the system preference via `matchMedia` and sets the corresponding class immediately.

### /arrange — P1: Coming Soon Placeholder Links
**Restyled** all 5 "Coming Soon" spans (4 footer nav items + "View on GitHub" CTA) with:
- `cursor: not-allowed` instead of `default`
- Lower opacity (0.4) + strikethrough text to clearly communicate unavailability
- `aria-disabled="true"` and `title="Not yet available"` for accessibility
- Hover tooltip via CSS `::after` pseudo-element explaining "Not yet available"

### /colorize — P2: Hero Stat Colors
**Unified** all 4 hero stat numbers (29, 22, 19, 16) to use `var(--blue)` instead of arbitrary cyan/violet/emerald/orange. This creates visual consistency — the numbers represent parallel data points with no semantic color distinction.

### /typeset — P2: "Engineering" Heading Tone
**Changed** the `<em>` in the hero h1 from `font-style: italic` with Instrument Serif to `font-family: var(--font-mono)` (DM Mono) with `font-style: normal`. This matches the developer-tool positioning with a monospace accent rather than an editorial serif italic.

### /arrange — P2: Agent Grid Monotony
**Restructured** the 12-agent flat grid into 4 semantic groups with category headers:
- **Security & Safety** (3 agents)
- **Performance & Architecture** (3 agents)
- **Code Quality & Testing** (3 agents)
- **Research & Workflow** (3 agents)

Changed from 4-column to 3-column grid. Replaced the dead "Coming Soon" button with a functional **expand/collapse** button that reveals 6 more agents with descriptions.

### /polish — P3: Version Credibility
**Replaced** "v1.0.0" in both the hero badge and footer with **"Preview"** label to honestly reflect the pre-release state while external resources (GitHub, docs) are still unavailable.
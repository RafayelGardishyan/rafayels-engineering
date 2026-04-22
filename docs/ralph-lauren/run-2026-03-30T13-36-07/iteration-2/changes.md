# Iteration 2 Changes

Good. All changes are applied. Here's a summary of everything I changed and the skills applied:

---

## Changes Applied (by priority)

### P0 — /harden
- **Fixed ALL 4 broken GitHub links**: The repo is private (confirmed via `gh api`), so external visitors get 404. Replaced all `github.com/RafayelGardishyan/rafayels-engineering` URLs with `github.com/marketplace/rafayels-engineering` (the public marketplace listing). Footer "Issues" link now uses `mailto:support@rafayels.engineering`.

### P1 — /arrange
- **Nav link visual rhythm**: Added `min-width: 80px` and `text-align: center` to nav links so spacing appears consistent regardless of text length.
- **Section padding dead zone**: Reduced `.section` padding from `--space-3xl` (64px) to `--space-2xl` (48px) and added `.section + .section { padding-top: var(--space-xl) }` to tighten the gap between terminal demo and "Built for Serious Work".

### P1 — /polish
- **Added og:image meta tags**: Added `og:image`, `og:image:width`, `og:image:height`, `og:image:alt`, and `twitter:image` meta tags pointing to `rafayels.engineering/og-card.png`.

### P1 — /typeset
- **Consolidated hero-sub paragraphs**: Merged the two `.hero-sub` paragraphs (which used a `calc(-1 * var(--space-md))` negative margin hack) into a single paragraph with proper flow.

### P1 — /optimize
- **Fixed font loading FOIT risk**: Converted the Google Fonts `<link>` to an async loading pattern using `onload="this.onload=null;this.rel='stylesheet'"` on the preload, with a `<noscript>` fallback.

### P2 — /harden
- **Changelog 'Soon' badge**: Moved from CSS `::before` pseudo-element (`content: 'Soon'`) to actual HTML `<span class="badge-soon">` with `aria-hidden="true"` — the parent already has `aria-label="Changelog — coming soon"`.

### P2 — /adapt
- **Pipeline arrow connectors**: At `@media (max-width: 1100px)` (3-column grid), now also hides the 5th step's arrow which was pointing right into nothing.

### P2 — /colorize
- **Increased blue-dim opacity**: `--blue-dim` from `0.3` → `0.45` and `--border-accent` from `0.3` → `0.4` for better card boundary definition on the dark background.

### P2 — /clarify
- **Hero stats context**: Added `title` attributes and small `.hero-stat-hint` descriptors ("autonomous reviewers", "reusable capabilities", "slash commands", "concurrent analysis") under each stat number.

### P2 — /bolder
- **Blueprint coordinate annotations**: Added `A1`/`F12` coordinate labels on corner marks and cross-hair `+` marks on sections, leaning harder into the engineering blueprint metaphor for brand differentiation.

### P2 — /normalize
- **Agent card font-size**: Changed hardcoded `12px` to `var(--text-xs)` token.
- **Section label alignment**: Added `padding-left: 2px` to `.section-label` for grid alignment.

### P3 — /typeset
- **Feature card h3 consistency**: Changed from `var(--font-body)` at weight 600 to `var(--font-display)` at weight 400, matching pipeline step headings for consistent h3 treatment.

### P3 — /arrange
- **Footer mobile centering**: Added `text-align: center; align-items: center` to footer and `justify-content: center; flex-wrap: wrap` to footer-links at `<900px` breakpoint.

### P3 — /animate
- **Terminal demo replay**: Changed from `unobserve` after first trigger to persistent observation — animation now resets when scrolled away and replays on re-entry.
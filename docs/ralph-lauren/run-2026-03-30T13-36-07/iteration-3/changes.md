# Iteration 3 Changes

The server is running and returning 200. Here's a summary of all changes applied:

---

## Changes Applied (by priority)

### P0 — /harden
- **Fixed all 5 broken GitHub Marketplace links** (`404` → valid URLs)
  - Marketplace, Documentation, +21 agents, View on Marketplace, bottom CTA all now point to `github.com/rafayels-engineering/rafayels-engineering`
  - Documentation link specifically points to `#readme`
  - Changelog link now points to `/releases` instead of showing vague "Soon" badge

### P1 — /typeset
- **Reduced type scale** to fix the jarring 5.3:1 ratio:
  - H1: `clamp(48px, 8vw, 96px)` → `clamp(40px, 6vw, 72px)`
  - H2: `clamp(32px, 5vw, 56px)` → `clamp(28px, 4vw, 44px)`
  - Bottom CTA H2: `clamp(28px, 4vw, 44px)` → `clamp(24px, 3.5vw, 36px)`

### P1 — /bolder + /arrange
- **Added SVG icons to all 5 pipeline steps** (clock, clipboard, code brackets, eye, book) — breaks up the text-heavy layout
- **Trimmed pipeline descriptions** to 1 line each for faster scanning
- **Increased pipeline gap** from 2px to 4px for better separation

### P1 — /clarify
- **Added "← run in Claude Code" hint** next to `/re:feature` command to explain the jargon to new users
- Moved hint styling to stylesheet class (`.hero-cmd-hint`) to reduce inline styles

### P1 — /colorize
- **Added full light mode** via `@media (prefers-color-scheme: light)` — complete palette override with appropriate surface colors, text colors, and component-specific adjustments
- **Fixed `--text-dim` contrast**: `#b0bcc8` → `#96a3b0` (ensures WCAG AA 4.5:1 compliance on dark background)

### P2 — /polish
- **Standardized hover states**: all text links (nav + footer) now get `text-decoration: underline` on hover, secondary CTA gets matching box-shadow lift

### P2 — /clarify
- **Replaced vague "Changelog Soon"** badge with a real link to GitHub Releases

### Pre-existing (verified working)
- ✅ Reduced motion support already in place (lines 1272-1285)
- ✅ Font preload with `onload` swap pattern already implemented
- ✅ Focus-visible styles already defined
- ✅ Clipboard API fallback for non-HTTPS already implemented
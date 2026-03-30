# Frontend Design Assessment Rubric

You are assessing a frontend page against six design quality dimensions. For each dimension, assign a score from 0-100 and list specific findings with severity ratings.

## Severity Ratings

- **P0 (Critical)**: Broken functionality, inaccessible content, unreadable text, completely wrong layout
- **P1 (Major)**: Poor usability, inconsistent patterns, significant visual issues
- **P2 (Minor)**: Polish issues, slight inconsistencies, minor spacing problems
- **P3 (Nit)**: Subjective improvements, micro-optimizations, nice-to-haves

## Dimension 1: Heuristics (Weight: 20%)

Score based on Nielsen's 10 Usability Heuristics:

1. **Visibility of system status** — Does the UI communicate what's happening? Loading states, active states, selected states, progress indicators.
2. **Match between system and real world** — Does it use language and concepts the user understands? Are metaphors appropriate?
3. **User control and freedom** — Can users undo, go back, escape? Are there emergency exits?
4. **Consistency and standards** — Do similar elements behave the same way? Are platform conventions followed?
5. **Error prevention** — Does the design prevent errors before they happen? Confirmations, constraints, smart defaults.
6. **Recognition rather than recall** — Is information visible when needed? Are options discoverable?
7. **Flexibility and efficiency** — Are there shortcuts for experts? Is the design efficient for both novice and experienced users?
8. **Aesthetic and minimalist design** — Is every element necessary? Is there visual noise?
9. **Help users recognize, diagnose, and recover from errors** — Are error messages helpful and actionable?
10. **Help and documentation** — Is help available when needed?

**Scoring**: 90-100 = Excellent on all heuristics. 70-89 = Good with minor violations. 50-69 = Several noticeable violations. Below 50 = Significant usability problems.

## Dimension 2: Typography (Weight: 15%)

- **Type scale**: Is there a consistent, intentional type scale (not random font sizes)?
- **Hierarchy**: Is the visual hierarchy clear? Can you scan and understand the content structure?
- **Line length**: Are lines of text between 45-75 characters for body text?
- **Line height**: Is line-height appropriate (1.4-1.6 for body, tighter for headings)?
- **Font pairing**: If multiple fonts are used, do they complement each other?
- **Weight usage**: Are font weights used purposefully (not too many, not random)?
- **Readability**: Is text easily readable at its displayed size and contrast?

**Scoring**: 90-100 = Professional typographic system. 70-89 = Good with minor issues. 50-69 = Inconsistent or problematic. Below 50 = Typography actively harms readability.

## Dimension 3: Layout (Weight: 20%)

- **Grid consistency**: Does the layout follow a consistent grid or alignment system?
- **Spacing rhythm**: Is spacing consistent and intentional (e.g., 4px/8px/16px/32px scale)?
- **Alignment**: Are elements properly aligned (not off by 1-2px)?
- **Whitespace**: Is whitespace used effectively — not too cramped, not too sparse?
- **Responsive awareness**: Does the layout appear to handle its current viewport well?
- **Content flow**: Does the layout guide the eye naturally through the content?
- **Component spacing**: Are gaps between components consistent and proportional?

**Scoring**: 90-100 = Pixel-perfect spatial system. 70-89 = Good with minor spacing issues. 50-69 = Noticeably inconsistent spacing. Below 50 = Chaotic or broken layout.

## Dimension 4: Color (Weight: 15%)

- **Palette coherence**: Does the page use a deliberate, limited color palette?
- **Contrast ratios**: Do text/background combinations meet WCAG AA (4.5:1 for normal text, 3:1 for large text)?
- **Semantic meaning**: Are colors used meaningfully (red=error, green=success, etc.)?
- **Harmony**: Do the colors work together aesthetically?
- **Neutral usage**: Are neutrals (grays, whites, blacks) well-chosen and consistent?
- **Accent restraint**: Are accent/brand colors used sparingly and purposefully?
- **State colors**: Are hover, active, focus, disabled states visually distinct?

**Scoring**: 90-100 = Sophisticated color system. 70-89 = Good palette with minor issues. 50-69 = Inconsistent or clashing colors. Below 50 = Color actively harms the experience.

## Dimension 5: Craft (Weight: 15%)

- **Border radii**: Are border radii consistent (same values throughout)?
- **Shadow system**: Are shadows consistent and purposeful (elevation system)?
- **Icon consistency**: Are icons from the same family, same size, same stroke weight?
- **Transitions**: Are state changes smooth (hover effects, focus rings)?
- **Loading states**: Are loading/skeleton states present where needed?
- **Empty states**: Are empty/null states handled gracefully?
- **Edge cases**: Are long text, missing images, and overflow handled?
- **Micro-interactions**: Is there attention to small details that delight?

**Scoring**: 90-100 = Impeccable attention to detail. 70-89 = Well-crafted with minor oversights. 50-69 = Noticeable lack of polish. Below 50 = Feels unfinished or broken.

## Dimension 6: Originality (Weight: 15%)

- **Distinctiveness**: Does this feel like a custom design, or a generic template?
- **Personality**: Does the design have a clear mood/identity/voice?
- **Custom decisions**: Are there intentional design choices (not just defaults)?
- **Avoids AI aesthetics**: Does it avoid telltale signs of AI-generated design (gratuitous gradients, generic hero sections, overuse of rounded cards)?
- **Brand coherence**: If there's a brand identity, does the design express it?
- **Creative confidence**: Are there bold choices that show design intention?

**Scoring**: 90-100 = Truly distinctive and memorable. 70-89 = Has personality with some generic elements. 50-69 = Mostly template-like. Below 50 = Indistinguishable from a default template.

## Overall Score Calculation

```
overall = (
    heuristics * 0.20 +
    typography * 0.15 +
    layout * 0.20 +
    color * 0.15 +
    craft * 0.15 +
    originality * 0.15
)
```

## Output Format

Your assessment MUST be a JSON code block:

```json
{
  "scores": {
    "heuristics": 0,
    "typography": 0,
    "layout": 0,
    "color": 0,
    "craft": 0,
    "originality": 0,
    "overall": 0
  },
  "findings": [
    {
      "dimension": "layout",
      "severity": "P1",
      "description": "Specific issue observed",
      "recommendation": "Specific fix suggestion"
    }
  ],
  "summary": "2-3 sentence overall assessment"
}
```

## Assessment Protocol

1. Navigate to the URL with agent-browser
2. Take a full-page screenshot for visual reference
3. Take an interactive snapshot to understand DOM structure
4. Score each dimension independently — be critical, not generous
5. List ALL findings you observe, not just the worst ones
6. Be specific in recommendations — reference actual elements, colors, sizes
7. The overall score should reflect honest quality, not encouragement

**Calibration**: A score of 50 means "average website". 70 means "good, professional quality". 85+ means "excellent, top-tier design". Be honest — most sites score 40-65.

"""Generate segmentation maps for screenshots using Gemini Vision.

Uses google/gemini-2.5-flash to analyze screenshots and produce detailed
segmentation maps that identify UI regions, components, and visual hierarchy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


SEGMENTATION_PROMPT = """Analyze this web page screenshot and create an extremely detailed segmentation map.
Generate a new image that is a color-coded segmentation overlay of the original, where:

- Each distinct UI component/region gets a unique, semi-transparent color overlay
- Label each region directly on the image with small text
- Use these color conventions:
  - Navigation/Header: blue overlay
  - Hero/Banner sections: purple overlay
  - Text content blocks: green overlay
  - Buttons/CTAs: red/orange overlay
  - Cards/tiles: cyan overlay
  - Icons/images: yellow overlay
  - Footer: gray overlay
  - Whitespace/padding: leave transparent
  - Form elements: pink overlay

Include labels for: padding gaps, alignment lines, grid structure, typography hierarchy levels,
color usage zones, interactive element boundaries, and any visual inconsistencies you notice.

Make the segmentation extremely detailed — every distinct visual element should be identified and labeled."""


async def generate_segmentation(
    screenshot_path: str | Path,
    output_path: str | Path,
) -> str | None:
    """Generate a segmentation map for a screenshot using Gemini Vision.

    Args:
        screenshot_path: Path to the screenshot PNG.
        output_path: Path to save the segmentation map.

    Returns:
        Text analysis from Gemini, or None if unavailable.
    """
    if not HAS_GEMINI:
        print("      [warn] google-genai or Pillow not installed — skipping segmentation", flush=True)
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("      [skip] GEMINI_API_KEY not set — skipping segmentation (set it or pass via --gemini-key)", flush=True)
        return None

    screenshot_path = Path(screenshot_path)
    if not screenshot_path.exists():
        print(f"      [warn] Screenshot not found: {screenshot_path} — skipping segmentation", flush=True)
        return None

    try:
        client = genai.Client(api_key=api_key)
        input_image = Image.open(screenshot_path)

        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        )

        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[SEGMENTATION_PROMPT, input_image],
            config=config,
        )

        text_response = None
        image_saved = False

        for part in response.parts:
            if part.text is not None:
                text_response = part.text
            elif part.inline_data is not None:
                image = part.as_image()
                image.save(str(output_path))
                image_saved = True

        if image_saved:
            print(f"      Segmentation map saved: {Path(output_path).name}", flush=True)
        else:
            print("      [warn] Gemini returned no image for segmentation", flush=True)

        return text_response

    except Exception as e:
        print(f"      [warn] Segmentation failed: {e}", flush=True)
        return None


async def generate_segmentation_for_dir(screenshot_dir: Path) -> None:
    """Generate segmentation maps for all screenshots in a directory."""
    for png in sorted(screenshot_dir.glob("screenshot*.png")):
        if "segmentation" in png.name:
            continue  # skip existing segmentation maps
        seg_path = png.with_name(png.stem + "-segmentation" + png.suffix)
        if not seg_path.exists():
            await generate_segmentation(png, seg_path)

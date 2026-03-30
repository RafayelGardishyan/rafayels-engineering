"""Generate segmentation maps for screenshots using MobileSAM.

Uses Meta's Segment Anything Model (MobileSAM variant) to produce
color-coded segmentation overlays of UI screenshots. Runs locally,
no API key needed, CPU-friendly (~40MB model).
"""

from __future__ import annotations

import asyncio
import urllib.request
from pathlib import Path

import numpy as np

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import torch
    from mobile_sam import SamAutomaticMaskGenerator, sam_model_registry
    HAS_SAM = True
except ImportError:
    HAS_SAM = False


WEIGHTS_URL = "https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt"
WEIGHTS_DIR = Path(__file__).parent / ".weights"
WEIGHTS_PATH = WEIGHTS_DIR / "mobile_sam.pt"

# Reuse loaded model across calls
_model = None
_generator = None


def _ensure_weights() -> bool:
    """Download MobileSAM weights if not present."""
    if WEIGHTS_PATH.exists():
        return True
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    print("      Downloading MobileSAM weights (~40MB)...", flush=True)
    try:
        urllib.request.urlretrieve(WEIGHTS_URL, str(WEIGHTS_PATH))
        print("      Weights downloaded.", flush=True)
        return True
    except Exception as e:
        print(f"      [warn] Failed to download MobileSAM weights: {e}", flush=True)
        return False


def _get_generator() -> SamAutomaticMaskGenerator | None:
    """Load MobileSAM model (cached across calls)."""
    global _model, _generator
    if _generator is not None:
        return _generator

    if not _ensure_weights():
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = sam_model_registry["vit_t"](checkpoint=str(WEIGHTS_PATH))
    _model.to(device=device)
    _model.eval()
    _generator = SamAutomaticMaskGenerator(_model)
    return _generator


def _create_overlay(image_np: np.ndarray, masks: list[dict]) -> np.ndarray:
    """Create a color-coded segmentation overlay on the image.

    Each mask gets a distinct semi-transparent color.
    Larger masks (background) get more transparent, smaller (UI elements) more opaque.
    """
    overlay = image_np.copy().astype(np.float64)

    # Sort masks by area descending — draw large (background) first, small (buttons) on top
    sorted_masks = sorted(masks, key=lambda m: m["area"], reverse=True)

    # Use a fixed color palette for consistency
    palette = [
        [66, 133, 244],   # blue (nav/header)
        [234, 67, 53],    # red (CTAs)
        [52, 168, 83],    # green (text blocks)
        [251, 188, 4],    # yellow (icons)
        [171, 71, 188],   # purple (hero sections)
        [0, 172, 193],    # cyan (cards)
        [255, 112, 67],   # orange (interactive)
        [158, 158, 158],  # gray (footer/chrome)
        [233, 30, 99],    # pink (forms)
        [139, 195, 74],   # light green
        [63, 81, 181],    # indigo
        [255, 193, 7],    # amber
        [0, 150, 136],    # teal
        [121, 85, 72],    # brown
        [96, 125, 139],   # blue-gray
        [244, 67, 54],    # deep red
    ]

    for i, mask_data in enumerate(sorted_masks):
        mask = mask_data["segmentation"]
        color = np.array(palette[i % len(palette)], dtype=np.float64)

        # Smaller areas = more opaque (they're UI elements), larger = more transparent
        area_ratio = mask_data["area"] / (image_np.shape[0] * image_np.shape[1])
        alpha = 0.25 if area_ratio > 0.1 else 0.45

        overlay[mask] = overlay[mask] * (1 - alpha) + color * alpha

    # Draw mask boundaries as thin lines
    for mask_data in sorted_masks:
        mask = mask_data["segmentation"].astype(np.uint8)
        # Find contours via simple edge detection
        edges_h = np.abs(np.diff(mask, axis=0, prepend=0))
        edges_v = np.abs(np.diff(mask, axis=1, prepend=0))
        boundary = (edges_h | edges_v).astype(bool)
        overlay[boundary] = [255, 255, 255]  # white boundary lines

    return np.clip(overlay, 0, 255).astype(np.uint8)


async def generate_segmentation(
    screenshot_path: str | Path,
    output_path: str | Path,
) -> bool:
    """Generate a segmentation map for a screenshot using MobileSAM.

    Args:
        screenshot_path: Path to the screenshot PNG.
        output_path: Path to save the segmentation overlay.

    Returns:
        True if segmentation was saved, False otherwise.
    """
    if not HAS_PIL:
        print("      [warn] Pillow not installed — skipping segmentation", flush=True)
        return False

    if not HAS_SAM:
        print("      [warn] mobile_sam not installed (pip install git+https://github.com/ChaoningZhang/MobileSAM.git) — skipping segmentation", flush=True)
        return False

    screenshot_path = Path(screenshot_path)
    if not screenshot_path.exists():
        print(f"      [warn] Screenshot not found: {screenshot_path}", flush=True)
        return False

    try:
        generator = _get_generator()
        if generator is None:
            return False

        # Load image as numpy array (RGB)
        image = Image.open(screenshot_path).convert("RGB")
        image_np = np.array(image)

        # Run segmentation (in a thread to not block async loop)
        loop = asyncio.get_event_loop()
        masks = await loop.run_in_executor(None, generator.generate, image_np)

        if not masks:
            print(f"      [warn] No masks generated for {screenshot_path.name}", flush=True)
            return False

        # Create overlay and save
        overlay = _create_overlay(image_np, masks)
        Image.fromarray(overlay).save(str(output_path))
        print(f"      Segmentation: {Path(output_path).name} ({len(masks)} regions)", flush=True)
        return True

    except Exception as e:
        print(f"      [warn] Segmentation failed: {e}", flush=True)
        return False


async def generate_segmentation_for_dir(screenshot_dir: Path) -> None:
    """Generate segmentation maps for all screenshots in a directory."""
    for png in sorted(screenshot_dir.glob("screenshot*.png")):
        if "segmentation" in png.name:
            continue
        seg_path = png.with_name(png.stem + "-segmentation" + png.suffix)
        if not seg_path.exists():
            await generate_segmentation(png, seg_path)

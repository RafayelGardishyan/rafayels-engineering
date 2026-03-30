"""Generate UI segmentation maps from DOM element bounding boxes.

Uses agent-browser to extract actual DOM element positions and roles,
then draws color-coded overlays with labels using Pillow. No ML model
needed — this is fast, free, deterministic, and semantically correct.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Map HTML tags/roles to colors and labels
ELEMENT_COLORS = {
    # Navigation
    "nav": (66, 133, 244, 80),       # blue
    "header": (66, 133, 244, 60),
    # Sections
    "section": (171, 71, 188, 50),   # purple
    "main": (171, 71, 188, 30),
    "article": (171, 71, 188, 50),
    # Interactive
    "button": (234, 67, 53, 100),    # red
    "a": (255, 112, 67, 70),         # orange
    "input": (233, 30, 99, 90),      # pink
    "textarea": (233, 30, 99, 90),
    "select": (233, 30, 99, 90),
    "form": (233, 30, 99, 50),
    # Content
    "h1": (52, 168, 83, 70),         # green
    "h2": (52, 168, 83, 60),
    "h3": (52, 168, 83, 50),
    "h4": (52, 168, 83, 40),
    "p": (139, 195, 74, 35),         # light green
    "ul": (139, 195, 74, 30),
    "ol": (139, 195, 74, 30),
    "li": (139, 195, 74, 25),
    # Media
    "img": (251, 188, 4, 80),        # yellow
    "svg": (251, 188, 4, 60),
    "video": (251, 188, 4, 80),
    "canvas": (251, 188, 4, 60),
    # Cards / containers
    "div": (0, 172, 193, 20),        # cyan (very light — divs are everywhere)
    # Footer
    "footer": (158, 158, 158, 60),   # gray
    # Code
    "pre": (96, 125, 139, 60),       # blue-gray
    "code": (96, 125, 139, 50),
    # Semantic
    "aside": (121, 85, 72, 50),      # brown
    "dialog": (244, 67, 54, 80),     # deep red
    "details": (0, 150, 136, 50),    # teal
}

# JS to extract all visible element bounding boxes
EXTRACT_ELEMENTS_JS = """
(() => {
    const results = [];
    const seen = new Set();
    // Target meaningful elements, skip generic wrappers
    const selectors = [
        'nav', 'header', 'footer', 'main', 'section', 'article', 'aside',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'p', 'a[href]', 'button', 'input', 'textarea', 'select', 'form',
        'img', 'svg', 'video', 'canvas',
        'ul', 'ol',
        'pre', 'code',
        'dialog', 'details',
        // Common UI patterns via class/role
        '[role="navigation"]', '[role="banner"]', '[role="main"]',
        '[role="complementary"]', '[role="contentinfo"]',
        '[role="button"]', '[role="link"]', '[role="listbox"]',
        // Cards and containers with meaningful classes
        '[class*="card"]', '[class*="Card"]',
        '[class*="hero"]', '[class*="Hero"]',
        '[class*="grid"]', '[class*="Grid"]',
        '[class*="modal"]', '[class*="Modal"]',
        '[class*="feature"]', '[class*="Feature"]',
        '[class*="pipeline"]', '[class*="Pipeline"]',
        '[class*="agent"]', '[class*="Agent"]',
    ];
    for (const sel of selectors) {
        try {
            for (const el of document.querySelectorAll(sel)) {
                if (seen.has(el)) continue;
                seen.add(el);
                const rect = el.getBoundingClientRect();
                // Skip invisible or tiny elements
                if (rect.width < 5 || rect.height < 5) continue;
                if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute('role') || '';
                const cls = el.className?.toString?.()?.slice(0, 50) || '';
                const text = (el.textContent || '').trim().slice(0, 30);
                results.push({
                    tag, role, cls, text,
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height),
                });
            }
        } catch(e) {}
    }
    return JSON.stringify(results);
})()
"""


def _get_color(element: dict) -> tuple[int, int, int, int]:
    """Get RGBA color for an element based on its tag/role."""
    role = element.get("role", "")
    tag = element.get("tag", "")
    cls = element.get("cls", "").lower()

    # Role-based overrides
    if role in ("navigation", "nav"):
        return ELEMENT_COLORS["nav"]
    if role == "banner":
        return ELEMENT_COLORS["header"]
    if role == "contentinfo":
        return ELEMENT_COLORS["footer"]
    if role == "button":
        return ELEMENT_COLORS["button"]

    # Class-based overrides
    if "card" in cls:
        return (0, 172, 193, 60)   # cyan, more opaque for cards
    if "hero" in cls:
        return (171, 71, 188, 60)  # purple
    if "feature" in cls:
        return (0, 172, 193, 50)
    if "grid" in cls or "pipeline" in cls:
        return (63, 81, 181, 40)   # indigo

    # Tag-based
    return ELEMENT_COLORS.get(tag, (128, 128, 128, 25))


def _get_label(element: dict) -> str:
    """Get a short label for an element."""
    tag = element.get("tag", "?")
    role = element.get("role", "")
    cls = element.get("cls", "")
    text = element.get("text", "")

    if role:
        return f"[{role}]"

    # Use class name if meaningful
    for keyword in ("card", "hero", "feature", "pipeline", "agent", "grid", "nav", "footer"):
        if keyword in cls.lower():
            return f".{keyword}"

    # Use tag + truncated text
    if text and tag in ("h1", "h2", "h3", "h4", "button", "a"):
        return f"<{tag}> {text[:20]}"

    return f"<{tag}>"


def _draw_overlay(
    image: Image.Image,
    elements: list[dict],
) -> Image.Image:
    """Draw color-coded element overlays on the image."""
    # Create RGBA overlay
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Try to get a small font for labels
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFCompact.ttf", 10)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except (OSError, IOError):
            font = ImageFont.load_default()

    # Sort: larger elements first (so smaller ones draw on top)
    sorted_elements = sorted(elements, key=lambda e: e["w"] * e["h"], reverse=True)

    for el in sorted_elements:
        x, y, w, h = el["x"], el["y"], el["w"], el["h"]
        r, g, b, a = _get_color(el)

        # Draw filled rectangle
        draw.rectangle([x, y, x + w, y + h], fill=(r, g, b, a))

        # Draw border (more opaque)
        draw.rectangle([x, y, x + w, y + h], outline=(r, g, b, min(a + 80, 255)), width=1)

        # Draw label (only for elements tall enough)
        if h > 14 and w > 30:
            label = _get_label(el)
            # Label background
            text_bbox = draw.textbbox((x + 2, y + 1), label, font=font)
            draw.rectangle(
                [text_bbox[0] - 1, text_bbox[1] - 1, text_bbox[2] + 1, text_bbox[3] + 1],
                fill=(0, 0, 0, 160),
            )
            draw.text((x + 2, y + 1), label, fill=(255, 255, 255, 220), font=font)

    # Composite onto original
    base = image.convert("RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")


def _infer_scroll_position(screenshot_path: Path) -> int | None:
    """Infer the scroll position from a screenshot filename.

    Convention from ralph_lauren.py:
      screenshot-0.png → scroll 0
      screenshot-1.png → scroll 800
      screenshot-2.png → scroll 1600
      screenshot-3.png → scroll 2400
      screenshot-footer.png → document.body.scrollHeight (use -1 sentinel)
    """
    name = screenshot_path.stem
    # screenshot-0, screenshot-1, etc.
    if name.startswith("screenshot-") and name[-1].isdigit():
        idx = int(name.split("-")[-1])
        return idx * 800
    if "footer" in name:
        return -1  # sentinel for scrollHeight
    return 0  # default to top


async def generate_segmentation(
    screenshot_path: str | Path,
    output_path: str | Path,
    url: str | None = None,
) -> bool:
    """Generate a DOM-based segmentation map for a screenshot.

    Scrolls agent-browser to match the screenshot's viewport position
    before extracting element bounding boxes.

    Args:
        screenshot_path: Path to the screenshot PNG.
        output_path: Path to save the segmentation overlay.
        url: If provided, open this URL in agent-browser first.

    Returns:
        True if segmentation was saved, False otherwise.
    """
    if not HAS_PIL:
        print("      [warn] Pillow not installed — skipping segmentation", flush=True)
        return False

    if not shutil.which("agent-browser"):
        print("      [warn] agent-browser not found — skipping segmentation", flush=True)
        return False

    screenshot_path = Path(screenshot_path)
    if not screenshot_path.exists():
        print(f"      [warn] Screenshot not found: {screenshot_path}", flush=True)
        return False

    try:
        # Open URL if provided
        if url:
            proc = await asyncio.create_subprocess_exec(
                "agent-browser", "open", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=15)

        # Scroll to match this screenshot's viewport position
        scroll_y = _infer_scroll_position(screenshot_path)
        if scroll_y == -1:
            scroll_cmd = "window.scrollTo(0, document.body.scrollHeight)"
        else:
            scroll_cmd = f"window.scrollTo(0, {scroll_y})"
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "eval", scroll_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
        await asyncio.sleep(0.5)  # let scroll animations settle

        # Extract element bounding boxes via JS (positions are relative to viewport)
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "eval", EXTRACT_ELEMENTS_JS,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        raw = stdout.decode().strip()

        # Parse JSON — agent-browser double-encodes (wraps in quotes)
        elements = None
        try:
            parsed = json.loads(raw)
            # If it parsed to a string, it was double-encoded — parse again
            if isinstance(parsed, str):
                elements = json.loads(parsed)
            elif isinstance(parsed, list):
                elements = parsed
        except json.JSONDecodeError:
            # Try line-by-line
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("[") or line.startswith('"['):
                    try:
                        p = json.loads(line)
                        elements = json.loads(p) if isinstance(p, str) else p
                        break
                    except (json.JSONDecodeError, TypeError):
                        continue

        if not elements:
            print(f"      [warn] Could not parse DOM elements from agent-browser", flush=True)
            return False

        if not elements:
            print(f"      [warn] No elements found on page", flush=True)
            return False

        # Load screenshot and draw overlay
        image = Image.open(screenshot_path).convert("RGB")
        result = _draw_overlay(image, elements)
        result.save(str(output_path))

        # Count element types
        tags = {}
        for el in elements:
            t = el.get("tag", "?")
            tags[t] = tags.get(t, 0) + 1
        tag_summary = ", ".join(f"{v} {k}" for k, v in sorted(tags.items(), key=lambda x: -x[1])[:5])

        print(f"      Segmentation: {Path(output_path).name} ({len(elements)} elements: {tag_summary})", flush=True)
        return True

    except Exception as e:
        print(f"      [warn] Segmentation failed: {e}", flush=True)
        return False


async def generate_segmentation_for_dir(screenshot_dir: Path, url: str | None = None) -> None:
    """Generate segmentation maps for all screenshots in a directory."""
    # Open the URL once, then scroll for each screenshot
    opened = False
    for png in sorted(screenshot_dir.glob("screenshot*.png")):
        if "segmentation" in png.name or "after" in png.name:
            continue
        seg_path = png.with_name(png.stem + "-segmentation" + png.suffix)
        if not seg_path.exists():
            # Only pass url on first call to avoid reopening
            await generate_segmentation(png, seg_path, url=url if not opened else None)
            opened = True

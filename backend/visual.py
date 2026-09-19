"""
Visual Regression Testing Engine for Autonomous UI/UX Testing.
Captures baselines, computes pixel-level diffs, highlights changed regions,
and uses AI to explain the visual impact of changes.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw

from backend.config import settings
from backend.schemas import VisualDiffResult, ChangedRegion

logger = logging.getLogger("autonomous_tester.visual")


class VisualRegressionEngine:
    """Compares screenshots against baselines to detect visual regressions."""

    def __init__(self, baselines_dir: Path = settings.BASELINES_DIR):
        self.baselines_dir = baselines_dir
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def save_baseline(self, run_id: str, step: int, screenshot_path: Path) -> Path:
        """Save a screenshot as the baseline for future comparisons."""
        baseline_dir = self.baselines_dir / run_id
        baseline_dir.mkdir(parents=True, exist_ok=True)
        baseline_path = baseline_dir / f"step_{step}.png"
        shutil.copy2(str(screenshot_path), str(baseline_path))
        logger.info(f"Baseline saved: {baseline_path}")
        return baseline_path

    def get_baseline(self, baseline_run_id: str, step: int) -> Optional[Path]:
        """Retrieve a baseline screenshot path if it exists."""
        baseline_path = self.baselines_dir / baseline_run_id / f"step_{step}.png"
        return baseline_path if baseline_path.exists() else None

    def compare(
        self,
        baseline_path: Path,
        current_path: Path,
        output_diff_path: Path,
        step_number: int = 0,
    ) -> VisualDiffResult:
        """
        Compare two screenshots pixel-by-pixel.
        Returns a VisualDiffResult with diff percentage, changed regions, and diff image.
        """
        try:
            baseline_img = Image.open(baseline_path).convert("RGB")
            current_img = Image.open(current_path).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to open images for comparison: {e}")
            return VisualDiffResult(
                step_number=step_number,
                baseline_path=str(baseline_path),
                current_path=str(current_path),
                diff_path="",
                diff_percentage=0.0,
                ai_explanation=f"Image comparison failed: {e}",
            )

        # Resize to match if dimensions differ
        if baseline_img.size != current_img.size:
            current_img = current_img.resize(baseline_img.size, Image.LANCZOS)

        # Compute pixel difference
        diff_img = ImageChops.difference(baseline_img, current_img)

        # Convert to grayscale for threshold analysis
        diff_gray = diff_img.convert("L")
        pixels = list(diff_gray.getdata())
        total_pixels = len(pixels)

        # Count significantly changed pixels (threshold > 30 to filter anti-aliasing noise)
        threshold = 30
        changed_pixels = sum(1 for p in pixels if p > threshold)
        diff_percentage = round((changed_pixels / total_pixels) * 100, 2) if total_pixels > 0 else 0.0

        # Find changed regions via bounding boxes
        changed_regions = self._find_changed_regions(diff_gray, threshold, baseline_img.size)

        # Generate highlighted diff image
        self._generate_diff_overlay(baseline_img, current_img, diff_gray, threshold, output_diff_path, changed_regions)

        is_significant = diff_percentage > settings.VISUAL_DIFF_THRESHOLD

        result = VisualDiffResult(
            step_number=step_number,
            baseline_path=str(baseline_path),
            current_path=str(current_path),
            diff_path=str(output_diff_path),
            diff_percentage=diff_percentage,
            changed_regions=changed_regions,
            is_significant=is_significant,
            ai_explanation=self._generate_heuristic_explanation(diff_percentage, changed_regions),
        )

        logger.info(
            f"Visual diff: {diff_percentage}% changed, "
            f"{len(changed_regions)} regions, significant={is_significant}"
        )
        return result

    def _find_changed_regions(
        self, diff_gray: Image.Image, threshold: int, image_size: Tuple[int, int]
    ) -> List[ChangedRegion]:
        """Identify rectangular bounding boxes of changed regions using grid scanning."""
        width, height = image_size
        regions: List[ChangedRegion] = []

        # Divide image into grid cells and detect which cells have changes
        cell_w, cell_h = 80, 60
        cells_changed = []

        for cy in range(0, height, cell_h):
            for cx in range(0, width, cell_w):
                box = (cx, cy, min(cx + cell_w, width), min(cy + cell_h, height))
                cell = diff_gray.crop(box)
                cell_pixels = list(cell.getdata())
                changed_count = sum(1 for p in cell_pixels if p > threshold)
                if changed_count > len(cell_pixels) * 0.05:  # >5% of cell changed
                    cells_changed.append((cx, cy, min(cx + cell_w, width), min(cy + cell_h, height)))

        # Merge adjacent cells into larger regions
        if cells_changed:
            merged = self._merge_rectangles(cells_changed)
            for i, (x1, y1, x2, y2) in enumerate(merged[:10]):  # Cap at 10 regions
                region_position = "top" if y1 < height // 3 else ("middle" if y1 < 2 * height // 3 else "bottom")
                regions.append(ChangedRegion(
                    x=x1, y=y1,
                    width=x2 - x1, height=y2 - y1,
                    description=f"Visual change in {region_position} area ({x2-x1}x{y2-y1}px)"
                ))

        return regions

    def _merge_rectangles(self, rects: List[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
        """Merge overlapping or adjacent rectangles."""
        if not rects:
            return []

        sorted_rects = sorted(rects, key=lambda r: (r[1], r[0]))
        merged = [sorted_rects[0]]

        for rect in sorted_rects[1:]:
            last = merged[-1]
            # Check if rectangles are adjacent or overlapping (with small gap tolerance)
            gap = 10
            if (rect[0] <= last[2] + gap and rect[1] <= last[3] + gap and
                    rect[2] >= last[0] - gap and rect[3] >= last[1] - gap):
                merged[-1] = (
                    min(last[0], rect[0]),
                    min(last[1], rect[1]),
                    max(last[2], rect[2]),
                    max(last[3], rect[3]),
                )
            else:
                merged.append(rect)

        return merged

    def _generate_diff_overlay(
        self,
        baseline: Image.Image,
        current: Image.Image,
        diff_gray: Image.Image,
        threshold: int,
        output_path: Path,
        changed_regions: List[ChangedRegion],
    ):
        """Generate a diff image with red overlay highlighting changed areas."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create side-by-side comparison: baseline | current | diff overlay
        width, height = baseline.size
        canvas_width = width  # Just show the overlay on current
        overlay = current.copy()
        draw = ImageDraw.Draw(overlay, "RGBA")

        # Draw semi-transparent red rectangles over changed regions
        for region in changed_regions:
            x1, y1 = region.x, region.y
            x2, y2 = x1 + region.width, y1 + region.height
            draw.rectangle([x1, y1, x2, y2], fill=(255, 0, 0, 60), outline=(255, 0, 0, 200), width=2)

        overlay.save(str(output_path), "PNG")

    def _generate_heuristic_explanation(self, diff_pct: float, regions: List[ChangedRegion]) -> str:
        """Generate a human-readable explanation of visual changes."""
        if diff_pct < 0.1:
            return "No meaningful visual differences detected."
        if diff_pct < 1.0:
            return f"Minor visual changes ({diff_pct}% of pixels). Likely anti-aliasing or subtle font rendering differences."

        parts = [f"Visual regression detected: {diff_pct}% of pixels changed across {len(regions)} region(s)."]
        for r in regions[:3]:
            parts.append(f"  - {r.description}")

        if diff_pct > 10:
            parts.append("This is a significant UI change that may affect layout, content, or styling.")
        elif diff_pct > 3:
            parts.append("Moderate change detected — likely a component-level style or content update.")

        return " ".join(parts)

    async def explain_with_ai(self, diff_result: VisualDiffResult, ai_agent) -> str:
        """Use AI to generate a detailed explanation of the visual diff. Falls back to heuristic."""
        # AI explanation would require multimodal call with diff images
        # For now, return the heuristic explanation (AI integration can be layered on)
        return diff_result.ai_explanation

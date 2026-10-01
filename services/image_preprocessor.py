"""Create learner-facing ECG images by masking configured text regions.

This module performs no OCR, ECG interpretation, or image synthesis. Redaction
regions must be reviewed for the source layout before processed images are used.
"""

from __future__ import annotations

import math
import os
import tempfile
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw, UnidentifiedImageError


# Shared initial header region for the three source layouts. It intentionally
# ends before the upper-right corner, where calibration information is expected.
HEADER_REDACTION_REGION = {"x": 0.02, "y": 0.015, "width": 0.70, "height": 0.15}
CASE_REDACTION_CONFIGS: dict[str, tuple[dict[str, float], ...]] = {
    "NSR_001": (),
    "SB_001": (),
    # Retain a reusable default for future image assets that have a verified
    # answer-revealing header in this source layout.
    "ST_001": (HEADER_REDACTION_REGION.copy(),),
}


class ImagePreprocessingError(ValueError):
    """Raised when the source image, output path, or mask config is invalid."""


def normalized_region_to_pixels(
    region: Mapping[str, Any], image_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Convert a normalized x/y/width/height region to pixel bounds (left, top, right, bottom)."""
    if not isinstance(region, Mapping) or not isinstance(image_size, tuple) or len(image_size) != 2:
        raise ImagePreprocessingError("A redaction region and (width, height) image size are required.")
    values = {key: region.get(key) for key in ("x", "y", "width", "height")}
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values.values()):
        raise ImagePreprocessingError("Redaction coordinates must be numeric values between 0.0 and 1.0.")
    if any(not math.isfinite(value) for value in values.values()):
        raise ImagePreprocessingError("Redaction coordinates must be finite numbers.")
    x, y, width, height = (Decimal(str(values[key])) for key in ("x", "y", "width", "height"))
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ImagePreprocessingError("Redaction regions must have positive size and stay within normalized image bounds.")
    image_width, image_height = image_size
    if (
        isinstance(image_width, bool)
        or isinstance(image_height, bool)
        or not isinstance(image_width, int)
        or not isinstance(image_height, int)
        or image_width <= 0
        or image_height <= 0
    ):
        raise ImagePreprocessingError("Image dimensions must be positive integers.")

    left = int((x * image_width).to_integral_value(rounding=ROUND_FLOOR))
    top = int((y * image_height).to_integral_value(rounding=ROUND_FLOOR))
    right = int(((x + width) * image_width).to_integral_value(rounding=ROUND_CEILING))
    bottom = int(((y + height) * image_height).to_integral_value(rounding=ROUND_CEILING))
    return left, top, min(right, image_width), min(bottom, image_height)


def _paper_background(image: Image.Image) -> tuple[int, int, int]:
    """Estimate paper color from image corners, avoiding ECG content in the center."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    patch_width = max(1, min(width // 20, 24))
    patch_height = max(1, min(height // 20, 24))
    samples: list[tuple[int, int, int]] = []
    for left, top in (
        (0, 0),
        (max(0, width - patch_width), 0),
        (0, max(0, height - patch_height)),
        (max(0, width - patch_width), max(0, height - patch_height)),
    ):
        patch = rgb.crop((left, top, left + patch_width, top + patch_height))
        samples.extend(list(patch.get_flattened_data()))
    return tuple(int(sorted(channel)[len(channel) // 2]) for channel in zip(*samples))


def create_learner_image(
    source_path: str | Path,
    output_path: str | Path,
    redaction_regions: Sequence[Mapping[str, Any]],
) -> Path:
    """Mask configured regions and save a same-size learner copy.

    The source is read only. If output points to the same file (including through
    a symlink or relative path), the function rejects the request rather than
    overwriting the source.
    """
    try:
        source = Path(source_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError) as exc:
        raise ImagePreprocessingError(f"ECG source image does not exist or cannot be accessed: {source_path}") from exc
    if not source.is_file():
        raise ImagePreprocessingError(f"ECG source path is not a file: {source}")
    try:
        output = Path(output_path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, TypeError) as exc:
        raise ImagePreprocessingError(f"Invalid learner image output path: {output_path}") from exc
    if output == source or (output.exists() and os.path.samefile(source, output)):
        raise ImagePreprocessingError("Output path must differ from the original source image.")
    if not isinstance(redaction_regions, Sequence) or isinstance(redaction_regions, (str, bytes)):
        raise ImagePreprocessingError("Redaction regions must be a sequence of normalized regions.")

    try:
        with Image.open(source) as opened:
            opened.load()
            image = opened.convert("RGB")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ImagePreprocessingError(f"Source is not a valid supported image: {source}") from exc

    boxes = [normalized_region_to_pixels(region, image.size) for region in redaction_regions]
    draw = ImageDraw.Draw(image)
    background = _paper_background(image)
    for left, top, right, bottom in boxes:
        # Pillow rectangle includes the right and bottom endpoints.
        draw.rectangle((left, top, right - 1, bottom - 1), fill=background)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        suffix = output.suffix.lower()
        image_format = Image.registered_extensions().get(suffix)
        if image_format is None:
            raise ImagePreprocessingError(f"Unsupported or missing output image extension: {suffix or '(none)'}")
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".ecg-learner-", suffix=suffix, dir=output.parent, delete=False) as temp:
                temporary_path = Path(temp.name)
            image.save(temporary_path, format=image_format)
            os.replace(temporary_path, output)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
    except ImagePreprocessingError:
        raise
    except (OSError, ValueError) as exc:
        raise ImagePreprocessingError(f"Could not save learner image to {output}: {exc}") from exc
    return output


def learner_output_path(source_path: str | Path, project_root: str | Path | None = None) -> Path | None:
    """Return the standard local learner-copy path for a source under assets/ecg/source."""
    root = Path(project_root).resolve() if project_root is not None else Path(__file__).resolve().parent.parent
    source = Path(source_path)
    if source.is_absolute() or source.drive:
        return None
    if len(source.parts) < 4 or source.parts[:3] != ("assets", "ecg", "source"):
        return None
    if any(part in {".", ".."} for part in source.parts):
        return None
    resolved_source = (root / source).resolve()
    try:
        resolved_source.relative_to((root / "assets" / "ecg" / "source").resolve())
    except ValueError:
        return None
    output = (root / "assets" / "ecg" / "learner" / f"{source.stem}_learner.png").resolve()
    try:
        output.relative_to((root / "assets" / "ecg" / "learner").resolve())
    except ValueError:
        return None
    return output

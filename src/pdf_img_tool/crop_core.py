from pathlib import Path
from typing import Literal

from PIL import Image

from pdf_img_tool.models import CropBox
from pdf_img_tool.utils import ensure_dir

RotationStep = Literal["left", "right", "half"]


def compute_display_scale(
    original_width: int,
    original_height: int,
    *,
    max_width: int,
    max_height: int,
) -> float:
    return min(max_width / original_width, max_height / original_height, 1.0)


def compute_display_size(
    original_width: int,
    original_height: int,
    scale: float,
) -> tuple[int, int]:
    width = max(1, round(original_width * scale))
    height = max(1, round(original_height * scale))
    return width, height


def clamp_point(x: int, y: int, *, max_width: int, max_height: int) -> tuple[int, int]:
    clamped_x = max(0, min(max_width, x))
    clamped_y = max(0, min(max_height, y))
    return clamped_x, clamped_y


def to_original_crop_box(
    display_box: CropBox,
    *,
    scale: float,
    original_width: int,
    original_height: int,
) -> CropBox:
    normalized = display_box.normalized()
    left = max(0, min(original_width, round(normalized.left / scale)))
    top = max(0, min(original_height, round(normalized.top / scale)))
    right = max(0, min(original_width, round(normalized.right / scale)))
    bottom = max(0, min(original_height, round(normalized.bottom / scale)))
    return CropBox(left=left, top=top, right=right, bottom=bottom).normalized()


def save_cropped_image(
    image: Image.Image,
    crop_box: CropBox,
    output_path: Path,
    *,
    output_format: str | None = None,
    jpeg_quality: int = 90,
) -> Path:
    ensure_dir(output_path.parent)
    cropped = image.crop((crop_box.left, crop_box.top, crop_box.right, crop_box.bottom))
    normalized_format = normalize_output_format(output_format, output_path=output_path)
    if normalized_format == "jpeg":
        if cropped.mode in {"RGBA", "LA", "P"}:
            cropped = cropped.convert("RGB")
        cropped.save(output_path, format="JPEG", quality=jpeg_quality)
    elif normalized_format == "png":
        cropped.save(output_path, format="PNG")
    else:
        cropped.save(output_path)
    return output_path


def normalize_output_format(output_format: str | None, *, output_path: Path) -> str | None:
    if output_format is None:
        return None

    lowered = output_format.lower()
    if lowered in {"jpg", "jpeg"}:
        return "jpeg"
    if lowered == "png":
        return "png"
    return output_path.suffix.lower().removeprefix(".")


def auto_trim_bbox(
    image: Image.Image,
    *,
    threshold: int,
    padding: int,
) -> CropBox | None:
    grayscale = image.convert("L")
    clamped_threshold = max(0, min(255, threshold))
    lookup_table = [255 if value < clamped_threshold else 0 for value in range(256)]
    binary = grayscale.point(lookup_table)
    bbox = binary.getbbox()
    if bbox is None:
        return None

    left, top, right, bottom = bbox
    if right <= left or bottom <= top:
        return None

    padded_left = max(0, left - padding)
    padded_top = max(0, top - padding)
    padded_right = min(image.width, right + padding)
    padded_bottom = min(image.height, bottom + padding)
    crop_box = CropBox(
        left=padded_left,
        top=padded_top,
        right=padded_right,
        bottom=padded_bottom,
    )
    return crop_box if crop_box.is_valid() else None


def rotate_crop_box(
    crop_box: CropBox,
    *,
    width: int,
    height: int,
    rotation: RotationStep,
) -> CropBox:
    box = crop_box.normalized()
    x0, y0, x1, y1 = box.left, box.top, box.right, box.bottom

    if rotation == "left":
        transformed = CropBox(
            left=y0,
            top=width - x1,
            right=y1,
            bottom=width - x0,
        )
    elif rotation == "right":
        transformed = CropBox(
            left=height - y1,
            top=x0,
            right=height - y0,
            bottom=x1,
        )
    else:
        transformed = CropBox(
            left=width - x1,
            top=height - y1,
            right=width - x0,
            bottom=height - y0,
        )

    return transformed.normalized()

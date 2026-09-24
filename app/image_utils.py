import io
import math
import uuid
from pathlib import Path
from PIL import Image, ImageOps

# Supported compression target range (KB)
MIN_TARGET_KB = 1
MAX_TARGET_KB = 100
DEFAULT_TARGET_KB = 50

# Longest side of the working image before compression starts
MAX_DIMENSION = 1920
# JPEG quality window used by the size search
MIN_QUALITY = 5
MAX_QUALITY = 95
# Safety bounds for the downscale retry loop
MAX_SCALE_ATTEMPTS = 12
MIN_DIMENSION = 48


def _encode(image: Image.Image, quality: int) -> io.BytesIO:
    """Encode a PIL image to an in-memory optimized JPEG buffer"""
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer


def _best_fitting_buffer(image: Image.Image, target_bytes: int):
    """
    Binary-search the highest JPEG quality whose encoded size still fits inside
    target_bytes. Returns (buffer, size, quality) or None when even MIN_QUALITY
    produces a file larger than the requested target.
    """
    low, high = MIN_QUALITY, MAX_QUALITY
    best = None
    while low <= high:
        mid = (low + high) // 2
        buffer = _encode(image, mid)
        size = buffer.tell()
        if size <= target_bytes:
            best = (buffer, size, mid)
            low = mid + 1
        else:
            high = mid - 1
    return best


def compress_and_save_image(
    file_bytes: bytes,
    original_filename: str,
    target_size_kb: int,
    uploads_dir: Path
) -> dict:
    """
    Compresses an image to match the user's requested target size (1KB - 100KB)
    and saves it as a JPEG file with a unique ID.

    The encoder never intentionally exceeds the target size: it searches for
    the highest quality fitting the target and, when the lowest quality is still
    too large (tiny targets such as 1KB), progressively downscales the
    resolution until the target is reached.

    Returns metadata dict: {id, original_name, filename, file_path, file_size_kb, target_size_kb, width, height}
    """
    # Clamp target size between 1KB and 100KB
    target_size_kb = max(MIN_TARGET_KB, min(MAX_TARGET_KB, int(target_size_kb)))
    target_bytes = target_size_kb * 1024

    # Open image using PIL
    img = Image.open(io.BytesIO(file_bytes))

    # Auto-orient based on EXIF tag if available
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Convert image to RGB format (JPEG does not support alpha/transparency or CMYK)
    if img.mode in ("RGBA", "LA", "P"):
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        rgb_img.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = rgb_img
    elif img.mode != "RGB":
        img = img.convert("RGB")

    width, height = img.size

    # Cap initial dimensions to avoid massive memory/computation if user uploaded huge photo (e.g., 4K/8K)
    if max(width, height) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(width, height)
        width = int(width * scale)
        height = int(height * scale)
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    # Compression search loop: find the best quality / resolution combination
    # that stays inside the requested target size.
    current_img = img
    best_buffer = None            # largest buffer found that fits the target
    best_size = 0
    best_dimensions = current_img.size

    # Always keep the smallest encode around as a last-resort fallback
    fallback_buffer = _encode(current_img, MIN_QUALITY)
    fallback_size = fallback_buffer.tell()
    fallback_dimensions = current_img.size

    for _ in range(MAX_SCALE_ATTEMPTS):
        fitted = _best_fitting_buffer(current_img, target_bytes)

        if fitted is not None:
            buffer, size, _quality = fitted
            if size > best_size:
                best_buffer = buffer
                best_size = size
                best_dimensions = current_img.size
            break

        # Even the lowest quality is above the target: measure it, then
        # downscale the resolution proportionally (JPEG size ~ pixel count).
        buffer = _encode(current_img, MIN_QUALITY)
        size = buffer.tell()
        if size < fallback_size:
            fallback_buffer = buffer
            fallback_size = size
            fallback_dimensions = current_img.size

        ratio = target_bytes / max(1, size)
        scale = min(0.9, max(0.25, math.sqrt(ratio)))
        new_w = max(MIN_DIMENSION, int(current_img.width * scale))
        new_h = max(MIN_DIMENSION, int(current_img.height * scale))

        if (new_w, new_h) == current_img.size:
            break

        current_img = current_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # If nothing fitted the target, fall back to the smallest encode produced
    if best_buffer is None:
        best_buffer = fallback_buffer
        best_dimensions = fallback_dimensions

    # Save to disk
    unique_id = uuid.uuid4().hex[:12]
    filename = f"{unique_id}.jpg"
    file_path = uploads_dir / filename

    file_bytes_out = best_buffer.getvalue()
    with open(file_path, "wb") as f:
        f.write(file_bytes_out)

    final_size_kb = len(file_bytes_out) / 1024.0

    return {
        "id": unique_id,
        "original_name": original_filename,
        "filename": filename,
        "file_path": str(file_path),
        "file_size_kb": final_size_kb,
        "target_size_kb": target_size_kb,
        "width": best_dimensions[0],
        "height": best_dimensions[1]
    }

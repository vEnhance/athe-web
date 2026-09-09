from io import BytesIO
from pathlib import Path
from typing import IO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_DIMENSION = 512
MAX_PIXELS = 50_000_000
JPEG_QUALITY = 85


def needs_downscaling(source: IO[bytes]) -> bool:
    """Whether this image is not already a JPEG fitting in the target box."""
    with Image.open(source) as image:
        return image.format != "JPEG" or max(image.size) > MAX_DIMENSION


def downscale_to_jpeg(source: IO[bytes], name: str) -> ContentFile[bytes]:
    """Re-encode an image as a JPEG fitting in a MAX_DIMENSION box.

    Camera rotation is applied, transparency is flattened onto white, and
    metadata is dropped. Images already smaller than the box keep their size.
    """
    with Image.open(source) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValidationError(
                f"That image is {image.width}x{image.height}, too large to process. "
                "Please scale it down before uploading."
            )
        # Must precede exif_transpose, which loads the pixels at full size.
        image.draft(None, (MAX_DIMENSION, MAX_DIMENSION))
        ImageOps.exif_transpose(image, in_place=True)
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

        opaque = image.convert("RGBA")
        flat = Image.new("RGB", opaque.size, "white")
        flat.paste(opaque, mask=opaque)

        buffer = BytesIO()
        flat.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)

    return ContentFile(buffer.getvalue(), name=f"{Path(name).stem}.jpg")

from io import BytesIO
from pathlib import Path
from typing import IO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from PIL.ExifTags import Base as ExifTag

STAFF_MAX_DIMENSION = 512
CONTENT_MAX_DIMENSION = 2048
MAX_PIXELS = 50_000_000
JPEG_QUALITY = 85


def _output_format(image: Image.Image, to_jpeg: bool) -> str:
    if to_jpeg:
        return "JPEG"
    if image.format not in ("JPEG", "PNG"):
        raise ValidationError(
            f"{image.format or 'That'} images cannot be resized in place; "
            "please convert to JPEG or PNG first."
        )
    return image.format


def needs_downscaling(
    source: IO[bytes], max_dimension: int, to_jpeg: bool = True
) -> bool:
    """Whether rewriting this image would gain anything.

    Formats we would have to rewrite in place but cannot re-encode, such as an
    animated GIF, are left alone rather than flattened or renamed.
    """
    with Image.open(source) as image:
        if image.format not in ("JPEG", "PNG") and not to_jpeg:
            return False
        if to_jpeg and image.format != "JPEG":
            return True
        if image.getexif().get(ExifTag.Orientation, 1) != 1:
            return True
        return max(image.size) > max_dimension


def downscale(
    source: IO[bytes], name: str, max_dimension: int, to_jpeg: bool = True
) -> ContentFile[bytes]:
    """Re-encode an image to fit in a max_dimension box, applying EXIF rotation.

    With to_jpeg, the result is always a JPEG with transparency flattened onto
    white, so the extension -- and therefore the file name -- changes. Without
    it the format is kept and the name is reusable, which weblog photos need:
    they are referenced by URL from inside post markdown, so renaming one
    breaks every post that uses it.
    """
    with Image.open(source) as image:
        fmt = _output_format(image, to_jpeg)
        if image.width * image.height > MAX_PIXELS:
            raise ValidationError(
                f"That image is {image.width}x{image.height}, too large to process. "
                "Please scale it down before uploading."
            )
        # Must precede exif_transpose, which loads the pixels at full size.
        image.draft(None, (max_dimension, max_dimension))
        ImageOps.exif_transpose(image, in_place=True)
        if image.mode == "P":
            # Palette images would otherwise be resized with NEAREST.
            image = image.convert("RGBA")
        image.thumbnail((max_dimension, max_dimension))

        if fmt == "JPEG":
            opaque = image.convert("RGBA")
            flat = Image.new("RGB", opaque.size, "white")
            flat.paste(opaque, mask=opaque)
            image = flat

        buffer = BytesIO()
        image.save(buffer, format=fmt, quality=JPEG_QUALITY, optimize=True)

    new_name = f"{Path(name).stem}.jpg" if to_jpeg else Path(name).name
    return ContentFile(buffer.getvalue(), name=new_name)

from typing import Any

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import models

from atheweb.images import downscale_to_jpeg

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class DownscaledImageFormField(forms.ImageField):
    """Image upload that is re-encoded to a small JPEG as it is cleaned."""

    def clean(self, data: Any, initial: Any = None) -> Any:
        if isinstance(data, UploadedFile) and (data.size or 0) > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(
                f"Keep uploads under {MAX_UPLOAD_BYTES // (1024 * 1024)} MB; "
                f"this one is {(data.size or 0) / (1024 * 1024):.1f} MB."
            )
        cleaned = super().clean(data, initial)
        if isinstance(cleaned, UploadedFile):
            return downscale_to_jpeg(cleaned, cleaned.name or "photo")
        return cleaned


class DownscaledImageField(models.ImageField):
    """ImageField whose uploads are re-encoded down to display size.

    The work happens in the form field, so it covers the admin and any
    ModelForm but leaves rows created directly through the ORM alone.
    """

    def formfield(self, **kwargs: Any) -> forms.Field | None:
        return super().formfield(**{"form_class": DownscaledImageFormField, **kwargs})

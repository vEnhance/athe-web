from collections.abc import Sequence
from typing import Any

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import models

from atheweb.images import STAFF_MAX_DIMENSION, downscale, needs_downscaling

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class DownscaledImageFormField(forms.ImageField):
    """Image upload that is re-encoded to fit its display size as it is cleaned."""

    def __init__(
        self,
        *args: Any,
        max_dimension: int = STAFF_MAX_DIMENSION,
        to_jpeg: bool = True,
        **kwargs: Any,
    ) -> None:
        self.max_dimension = max_dimension
        self.to_jpeg = to_jpeg
        super().__init__(*args, **kwargs)

    def clean(self, data: Any, initial: Any = None) -> Any:
        if isinstance(data, UploadedFile) and (data.size or 0) > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(
                f"Keep uploads under {MAX_UPLOAD_BYTES // (1024 * 1024)} MB; "
                f"this one is {(data.size or 0) / (1024 * 1024):.1f} MB."
            )
        cleaned = super().clean(data, initial)
        if not isinstance(cleaned, UploadedFile):
            return cleaned
        if not needs_downscaling(cleaned, self.max_dimension, self.to_jpeg):
            return cleaned
        cleaned.seek(0)
        return downscale(
            cleaned, cleaned.name or "photo", self.max_dimension, self.to_jpeg
        )


class DownscaledImageField(models.ImageField):
    """ImageField whose uploads are re-encoded down to the size they display at.

    The work happens in the form field, so it covers the admin and any
    ModelForm but leaves rows created directly through the ORM alone.
    """

    def __init__(
        self,
        *args: Any,
        max_dimension: int = STAFF_MAX_DIMENSION,
        to_jpeg: bool = True,
        **kwargs: Any,
    ) -> None:
        self.max_dimension = max_dimension
        self.to_jpeg = to_jpeg
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        if self.max_dimension != STAFF_MAX_DIMENSION:
            kwargs["max_dimension"] = self.max_dimension
        if not self.to_jpeg:
            kwargs["to_jpeg"] = False
        return name, path, args, kwargs

    def formfield(self, **kwargs: Any) -> forms.Field | None:
        return super().formfield(
            **{
                "form_class": DownscaledImageFormField,
                "max_dimension": self.max_dimension,
                "to_jpeg": self.to_jpeg,
                **kwargs,
            }
        )

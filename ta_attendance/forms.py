from django import forms
from django.utils import timezone

from courses.models import Course

from .models import Attendance


class AttendanceForm(forms.ModelForm):
    """Form for staff to log their attendance at a club."""

    class Meta:
        model = Attendance
        fields = ["date", "club"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        # Default date to today
        self.fields["date"].initial = timezone.localdate()
        self.fields["club"].queryset = (  # type: ignore[attr-defined]
            Course.objects.clubs()
            .unfinished()
            .select_related("semester")
            .order_by("semester__name", "name")
        )

from django import forms
from courses.models import CourseMeeting


class CourseMeetingForm(forms.ModelForm):
    """Form for creating/editing course meetings."""

    class Meta:
        model = CourseMeeting
        fields = ["start_time", "title"]
        widgets = {
            "start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "title": forms.TextInput(attrs={"placeholder": "Meeting topic (optional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the datetime input more user-friendly
        if self.instance and self.instance.pk:
            self.initial["start_time"] = self.instance.start_time.strftime(
                "%Y-%m-%dT%H:%M"
            )

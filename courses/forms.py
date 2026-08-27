from typing import Any

from django import forms
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester, Student


class CourseMeetingForm(forms.ModelForm):  # type: ignore[type-arg]
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Display existing datetime in the website's timezone (America/New_York)
        if self.instance and self.instance.pk:
            local_time = timezone.localtime(self.instance.start_time)
            self.initial["start_time"] = local_time.strftime("%Y-%m-%dT%H:%M")

    def clean_start_time(self) -> Any:
        """Convert naive datetime from datetime-local input to aware datetime in website's timezone."""
        start_time = self.cleaned_data["start_time"]
        if start_time and timezone.is_naive(start_time):
            # datetime-local provides naive datetime; interpret it in website's timezone
            start_time = timezone.make_aware(
                start_time, timezone.get_current_timezone()
            )
        return start_time


class CourseUpdateForm(forms.ModelForm):  # type: ignore[type-arg]
    """Form for updating course details, for whoever runs the course."""

    class Meta:
        model = Course
        fields = [
            "description",
            "difficulty",
            "lesson_plan",
            "regular_meeting_time",
            "google_classroom_direct_link",
            "zoom_meeting_link",
            "discord_webhook",
            "discord_role_id",
            "discord_reminders_enabled",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "lesson_plan": forms.Textarea(
                attrs={"rows": 8, "placeholder": "One lesson per line"}
            ),
            "regular_meeting_time": forms.TextInput(
                attrs={"placeholder": "e.g. 5pm-6pm ET on Saturday"}
            ),
            "google_classroom_direct_link": forms.URLInput(
                attrs={"placeholder": "https://classroom.google.com/..."}
            ),
            "zoom_meeting_link": forms.URLInput(
                attrs={"placeholder": "https://zoom.us/..."}
            ),
            "discord_webhook": forms.URLInput(
                attrs={"placeholder": "https://discord.com/api/webhooks/..."}
            ),
            "discord_role_id": forms.TextInput(
                attrs={"placeholder": "Discord role ID for mentions"}
            ),
        }
        help_texts = {
            "description": "Brief description of the course/club",
            "difficulty": "Estimate of difficulty level",
            "lesson_plan": "List of lessons planned for this course (one per line)",
            "regular_meeting_time": "Regular meeting time, e.g. '5pm-6pm ET on Saturday'",
            "google_classroom_direct_link": "Direct link to Google Classroom",
            "zoom_meeting_link": "Zoom meeting link for this course",
            "discord_webhook": "Discord webhook URL for posting reminders",
            "discord_role_id": "Discord role ID to mention in reminders",
            "discord_reminders_enabled": "Whether to send Discord reminders",
        }


class BulkStudentCreationForm(forms.Form):
    """Form for bulk creation of students from a list of Airtable names.

    Classes and houses are not set here: students fill in the registration
    questionnaire first, and the computed matching is uploaded afterwards.
    """

    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        help_text="Select the semester for these students",
    )
    student_data = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 15,
                "placeholder": "One airtable_name per line:\nAlice Anderson\nBob Brown",
            }
        ),
        label="Student names",
        help_text="One airtable_name per line, exactly as it appears in Airtable",
    )

    def clean(self) -> dict[str, Any]:
        """Parse student_data into a list of names.

        Every line is checked before any is accepted, so a typo halfway down
        the paste does not leave the first half created.
        """
        cleaned = super().clean() or {}
        semester = cleaned.get("semester")
        if semester is None or "student_data" not in cleaned:
            return cleaned

        if semester.end_date < timezone.now().date():
            raise forms.ValidationError(
                f"Cannot create students for {semester.name} - semester has ended."
            )

        names: list[str] = []
        errors: list[str] = []
        for number, raw in enumerate(cleaned["student_data"].strip().splitlines(), 1):
            name = raw.strip()
            if not name:
                continue
            if len(name) > Student.NAME_MAX_LENGTH:
                errors.append(f"Line {number}: '{name}' is too long for a name.")
            elif name in names:
                errors.append(f"Line {number}: '{name}' is listed twice.")
            else:
                names.append(name)

        if errors:
            raise forms.ValidationError(errors)

        cleaned["students"] = names
        return cleaned

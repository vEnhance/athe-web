from typing import Any

from django import forms
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester


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
    """Form for updating course details by leaders."""

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
    """Form for bulk creation of students with course enrollments."""

    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        help_text="Select the semester for these students",
    )
    student_data = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 15,
                "placeholder": "Each line: airtable_name[TAB]course1,course2,course3\n"
                "Example:\n"
                "Alice Anderson\tAlgebra,Geometry\n"
                "Bob Brown\tCalculus",
            }
        ),
        help_text="Each line should contain: airtable_name (tab) comma-separated course names",
    )


class SortingHatForm(forms.Form):
    """Form for bulk house assignment to students."""

    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        help_text="Select the semester for house assignment",
    )

    blob = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one airtable_name per line"}
        ),
        label="Blob",
        help_text="Students to assign to Blob house",
    )

    cat = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one airtable_name per line"}
        ),
        label="Cat",
        help_text="Students to assign to Cat house",
    )

    owl = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one airtable_name per line"}
        ),
        label="Owl",
        help_text="Students to assign to Owl house",
    )

    red_panda = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one airtable_name per line"}
        ),
        label="Red Panda",
        help_text="Students to assign to Red Panda house",
    )

    bunny = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one airtable_name per line"}
        ),
        label="Bunny",
        help_text="Students to assign to Bunny house",
    )

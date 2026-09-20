from typing import Any

from django import forms
from django.db.models import QuerySet
from django.utils import timezone

from courses.models import CourseMeeting

from .models import MEETING_HORIZON_DAYS, Ticket

DM_LABEL = "via Discord DM"


def meeting_choices() -> QuerySet[CourseMeeting]:
    return CourseMeeting.objects.office_hours_within(MEETING_HORIZON_DAYS).order_by(
        "start_time"
    )


class MeetingChoiceField(forms.ModelChoiceField):
    """The office hours dropdown, whose blank choice means "over Discord"."""

    def label_from_instance(self, obj: CourseMeeting) -> str:
        when = timezone.localtime(obj.start_time)
        return f"{obj.course.name} — {when:%a %b %-d, %-I:%M %p %Z}"


class TicketForm(forms.ModelForm):  # type: ignore[type-arg]
    meeting = MeetingChoiceField(
        queryset=CourseMeeting.objects.none(),
        required=False,
        blank=True,
        empty_label=DM_LABEL,
        label="Where should we answer this?",
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Ticket
        fields = ["title", "question", "meeting"]
        labels = {"title": "Question title", "question": "Your question"}
        widgets = {
            "question": forms.Textarea(
                attrs={
                    "rows": 10,
                    "placeholder": "Write your question here. LaTeX like $x^2+1$ "
                    "will be typeset.",
                }
            ),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["meeting"].queryset = meeting_choices()  # type: ignore[attr-defined]


class TicketReviewForm(forms.ModelForm):  # type: ignore[type-arg]
    """What staff may change on a ticket: whether it is done, and their notes."""

    resolved = forms.BooleanField(required=False, label="Mark as resolved")

    class Meta:
        model = Ticket
        fields = ["staff_notes"]
        widgets = {"staff_notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["resolved"].initial = self.instance.is_resolved

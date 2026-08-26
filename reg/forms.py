import json
from collections.abc import Iterable
from typing import Any, NamedTuple

from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.db import transaction

from courses.models import Course, Semester, Student
from home.models import StaffPhotoListing

from . import availability
from .models import CoursePreference, StudentRegistration


class Assignment(NamedTuple):
    """One student's computed placement, as read out of Greta's JSON."""

    student: Student
    #: Classes to enroll the student in, or None to leave enrollments alone.
    courses: list[Course] | None
    #: House to sort the student into, or None to leave the house alone.
    house: Student.House | None


#: Shown in the upload box to demonstrate the shape expected of the JSON.
EXAMPLE_PAYLOAD = """{
  "semester": "spring-2026",
  "assignments": [
    {"airtable_name": "Alice Anderson",
     "courses": ["Algebra", "Geometry"], "house": "owl"},
    {"airtable_name": "Bob Brown", "courses": ["Calculus"], "house": "cat"}
  ]
}"""


class StaffSelectionForm(forms.Form):
    """Form for selecting which StaffPhotoListing the user corresponds to."""

    staff_listing = forms.ModelChoiceField(
        queryset=StaffPhotoListing.objects.exclude(
            category=StaffPhotoListing.Category.XSTAFF
        ),
        widget=forms.RadioSelect,
        label="Who are you?",
        help_text="Please select which staff member you are from the list below.",
    )


class RegistrationForm(UserCreationForm):  # type: ignore[type-arg]
    """Base account-creation form: real name and email are required."""

    email = forms.EmailField(
        required=True,
        help_text="Required. Enter your email address.",
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        help_text="Required. Enter your first name.",
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        help_text="Required. Enter your last name.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]
        # UserCreationForm.Meta sets this; subclasses that override Meta without
        # inheriting it silently fall back to a plain CharField.
        field_classes = {"username": UsernameField}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields[
            "username"
        ].help_text = (
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        )
        self.fields["password1"].help_text = (
            "Your password must contain at least 8 characters "
            "and can't be entirely numeric."
        )
        self.fields[
            "password2"
        ].help_text = "Enter the same password as before, for verification."


class StaffRegistrationForm(RegistrationForm):
    """Form for creating a new staff user account."""

    class Meta(RegistrationForm.Meta):
        # NB: the two registration forms order their fields differently.
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        ]


class StudentRegistrationForm(RegistrationForm):
    """Form for creating a new student user account."""

    class Meta(RegistrationForm.Meta):
        fields = [
            "username",
            "password1",
            "password2",
            "email",
            "first_name",
            "last_name",
        ]


class LoginChoiceForm(forms.Form):
    """Form for choosing whether to login or create a new account."""

    HAS_ACCOUNT_CHOICES = [
        ("yes", "Yes, I have an account from a previous year and will log in"),
        ("no", "No, I am joining Athemath for the first time"),
    ]

    has_account = forms.ChoiceField(
        choices=HAS_ACCOUNT_CHOICES,
        widget=forms.RadioSelect,
        label="Do you already have an account from a previous Athemath?",
        help_text="Select whether you have an existing account or need to create a new one.",
    )


class AvailabilityGridWidget(forms.Widget):
    """A when2meet-style grid of checkboxes, one row per half hour.

    Real checkboxes rather than a JavaScript-only applet: the accompanying
    script only adds click-and-drag painting on top, so the grid still works
    (tediously) with scripting off. It deliberately does not subclass
    CheckboxSelectMultiple, which django-bootstrap5 re-templates as a stack of
    64 labelled rows.
    """

    template_name = "reg/widgets/availability_grid.html"
    allow_multiple_selected = True

    def value_from_datadict(self, data: Any, files: Any, name: str) -> Any:
        # Same handling SelectMultiple gives a plain dict versus a QueryDict.
        getter = getattr(data, "getlist", data.get)
        return getter(name)

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        chosen = {str(slot) for slot in value or ()}
        context["widget"]["grid"] = {
            "days": [label for _, label in availability.DAYS],
            "rows": [
                {
                    "label": availability.time_label(start),
                    "cells": [
                        {
                            "key": availability.slot_key(day, start),
                            "label": availability.slot_label(day, start),
                            "checked": availability.slot_key(day, start) in chosen,
                        }
                        for day, _ in availability.DAYS
                    ],
                }
                for start in availability.slot_starts()
            ],
        }
        return context


class AvailabilityField(forms.MultipleChoiceField):
    """The weekend availability grid, stored as a list of slot keys."""

    widget = AvailabilityGridWidget

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("choices", availability.slot_choices())
        kwargs.setdefault("label", "When are you available?")
        kwargs.setdefault(
            "help_text",
            "All times are Eastern. Click and drag to paint the times you could "
            "attend a class. Mark everything you could make, not just your "
            "favorites: the more you mark, the easier you are to schedule.",
        )
        super().__init__(**kwargs)


#: One student's verdict on one class: a rank, or a refusal.
type Preference = tuple[Course, int | None, bool]


class CoursePreferenceWidget(forms.Widget):
    """Renders the ranked list of classes and the "no thanks" pile beside it.

    The ranking rides on the DOM order of hidden inputs, which is the order the
    browser submits them in. That way the drag-and-drop script has nothing to
    serialize, and a browser running no script at all still posts a complete
    ranking (the order the classes were rendered in) with the exclusion boxes
    working normally.
    """

    template_name = "reg/widgets/course_preferences.html"

    def __init__(
        self, courses: Iterable[Course] = (), attrs: dict[str, Any] | None = None
    ) -> None:
        super().__init__(attrs)
        self.courses = list(courses)

    @staticmethod
    def excluded_name(name: str) -> str:
        """Name of the companion checkbox input for the exclusion pile."""
        return f"{name}_excluded"

    def value_from_datadict(
        self, data: Any, files: Any, name: str
    ) -> dict[str, list[str]]:
        get_list = getattr(data, "getlist", lambda key, default=(): list(default))
        return {
            "order": [str(pk) for pk in get_list(name)],
            "excluded": [str(pk) for pk in get_list(self.excluded_name(name))],
        }

    def rows(self, value: Any) -> list[dict[str, Any]]:
        """The classes in submitted order, each tagged with its exclusion.

        Anything the submission left out (or invented) is ignored and the
        missing classes are appended, so the rendered list always covers the
        semester exactly once.
        """
        by_pk = {str(course.pk): course for course in self.courses}
        value = value or {}
        ordered: list[Course] = []
        seen: set[str] = set()
        for pk in value.get("order", ()):
            if pk in by_pk and pk not in seen:
                seen.add(pk)
                ordered.append(by_pk[pk])
        ordered += [c for c in self.courses if str(c.pk) not in seen]

        excluded = set(value.get("excluded", ()))
        return [
            {"course": course, "excluded": str(course.pk) in excluded}
            for course in ordered
        ]

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        rows = self.rows(value)
        context["widget"].update(
            excluded_name=self.excluded_name(name),
            ranked=[row["course"] for row in rows if not row["excluded"]],
            excluded=[row["course"] for row in rows if row["excluded"]],
        )
        return context


class CoursePreferenceField(forms.Field):
    """Turns the ranked list into ``(course, rank, excluded)`` triples."""

    widget = CoursePreferenceWidget

    def __init__(self, *, courses: Iterable[Course], **kwargs: Any) -> None:
        self.courses = list(courses)
        kwargs.setdefault("label", "Rank the classes you'd like to take")
        super().__init__(**kwargs)
        self.widget.courses = self.courses

    @staticmethod
    def initial_for(registration: StudentRegistration) -> dict[str, list[str]]:
        """The widget value that redisplays an already-saved set of answers."""
        preferences = list(
            CoursePreference.objects.filter(registration=registration).select_related(
                "course"
            )
        )
        return {
            "order": [str(pref.course.pk) for pref in preferences],
            "excluded": [str(pref.course.pk) for pref in preferences if pref.excluded],
        }

    def clean(self, value: Any) -> list[Preference]:
        rows = self.widget.rows(value)
        preferences: list[Preference] = []
        rank = 0
        for row in rows:
            if row["excluded"]:
                preferences.append((row["course"], None, True))
            else:
                rank += 1
                preferences.append((row["course"], rank, False))

        if self.required and not rank:
            raise forms.ValidationError(
                "Please leave at least one class you would be willing to take."
            )
        return preferences


class StudentQuestionnaireForm(forms.ModelForm):  # type: ignore[type-arg]
    """Everything a student tells us at registration, on one page.

    In *create* mode the student also picks their name off the roster, which is
    what binds their account to a Student record; in *edit* mode the name is
    already settled and only the answers can change.
    """

    taken_class_before = forms.TypedChoiceField(
        choices=(("yes", "Yes"), ("no", "No")),
        coerce=lambda value: value == "yes",
        widget=forms.RadioSelect,
        label="Have you taken an Athemath class before?",
    )
    availability = AvailabilityField()

    class Meta:
        model = StudentRegistration
        fields = [
            "email",
            "parent_email",
            "discord_username",
            "taken_class_before",
            "course_comments",
            "availability",
            "availability_comments",
            "quiz_challenge",
            "quiz_values",
            "quiz_compass",
            "quiz_day_off",
            "quiz_friend",
            "house_request",
        ]
        widgets = {
            "course_comments": forms.Textarea(attrs={"rows": 3}),
            "availability_comments": forms.Textarea(attrs={"rows": 3}),
            "house_request": forms.Textarea(attrs={"rows": 3}),
            "quiz_challenge": forms.RadioSelect,
            "quiz_values": forms.RadioSelect,
            "quiz_compass": forms.RadioSelect,
            "quiz_day_off": forms.RadioSelect,
            "quiz_friend": forms.RadioSelect,
        }
        labels = {
            "course_comments": "Anything else about your class preferences?",
            "availability_comments": "Anything else about your availability?",
        }

    #: Questions of the sorting ceremony, in the order they are asked.
    QUIZ_FIELDS = (
        "quiz_challenge",
        "quiz_values",
        "quiz_compass",
        "quiz_day_off",
        "quiz_friend",
    )

    def __init__(
        self,
        *args: Any,
        semester: Semester,
        student: Student | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.semester = semester
        self.claimed_student = student

        # Every quiz question must be answered, so a model-supplied blank
        # choice would just be an unlabelled sixth radio button.
        for name in self.QUIZ_FIELDS:
            field = self.fields[name]
            field.choices = [  # type: ignore[attr-defined]
                choice
                for choice in field.choices  # type: ignore[attr-defined]
                if choice[0]
            ]

        classes = Course.objects.filter(semester=semester, is_club=False).order_by(
            "name"
        )
        self.fields["course_preferences"] = CoursePreferenceField(
            courses=classes,
            # A semester whose classes are not up yet should not be a dead end.
            required=classes.exists(),
        )
        if student is None:
            # The whole roster is offered, claimed names included; picking a
            # claimed one is rejected by clean_student() below.
            self.fields["student"] = forms.ModelChoiceField(
                queryset=Student.objects.filter(semester=semester),
                widget=forms.RadioSelect,
                empty_label=None,
                label="Who are you?",
                help_text="Please select your name from the roster below.",
            )
        elif self.instance.pk:
            self.initial["course_preferences"] = CoursePreferenceField.initial_for(
                self.instance
            )

    def quiz_fields(self) -> list[Any]:
        """The sorting questions as bound fields, for the template to loop over."""
        return [self[name] for name in self.QUIZ_FIELDS]

    def clean_student(self) -> Student:
        student = self.cleaned_data["student"]
        if student.user is not None:
            raise forms.ValidationError(
                f"{student.airtable_name} has already been claimed by someone else. "
                "If you think this is a mistake, please contact us."
            )
        return student

    @transaction.atomic
    def save_registration(self, user: User) -> Student:
        """Bind the user to their Student and store this set of answers."""
        student = self.claimed_student or self.cleaned_data["student"]
        if student.user != user:
            student.user = user
            student.save()

        registration = super().save(commit=False)
        registration.student = student
        registration.save()

        # Simpler to lay the preferences down fresh than to diff them, and it
        # keeps a re-submission from leaving stale ranks behind.
        CoursePreference.objects.filter(registration=registration).delete()
        CoursePreference.objects.bulk_create(
            CoursePreference(
                registration=registration, course=course, rank=rank, excluded=excluded
            )
            for course, rank, excluded in self.cleaned_data["course_preferences"]
        )
        return student


class AssignmentUploadForm(forms.Form):
    """The computed matching of students to classes and houses, as JSON.

    Accepts either the object the download endpoint's format implies::

        {"semester": "spring-2026", "assignments": [...]}

    or a bare list of assignment objects. Each one names a student by
    ``airtable_name`` (or by the ``id`` from the download) and may carry
    ``courses`` and/or ``house``; whichever key is absent is left alone.
    """

    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        help_text="The semester these assignments are for",
    )
    payload = forms.CharField(
        required=False,
        label="JSON",
        widget=forms.Textarea(attrs={"rows": 15, "placeholder": EXAMPLE_PAYLOAD}),
        help_text="Paste the computed assignments here, or upload a file below.",
    )
    payload_file = forms.FileField(
        required=False,
        label="JSON file",
        help_text="Used instead of the box above, if given.",
    )

    def _raw_payload(self) -> str:
        """The JSON text to read, preferring an uploaded file over the box."""
        uploaded = self.cleaned_data.get("payload_file")
        if uploaded is not None:
            try:
                return uploaded.read().decode("utf-8")
            except UnicodeDecodeError as error:
                raise forms.ValidationError(
                    f"Could not read the uploaded file as UTF-8 text: {error}"
                ) from error
        return self.cleaned_data.get("payload", "")

    @staticmethod
    def _entries(payload: Any, semester: Semester) -> list[Any]:
        """Pull the list of assignments out of either accepted shape."""
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise forms.ValidationError(
                "Expected a JSON object or a JSON list at the top level."
            )
        named = payload.get("semester")
        if isinstance(named, dict):
            named = named.get("slug")
        if named is not None and named not in (semester.slug, semester.name):
            raise forms.ValidationError(
                f"This JSON says it is for '{named}', "
                f"but '{semester.slug}' is selected above."
            )
        entries = payload.get("assignments")
        if not isinstance(entries, list):
            raise forms.ValidationError(
                "Expected an 'assignments' key holding a list of assignments."
            )
        return entries

    def clean(self) -> dict[str, Any]:
        """Resolve every assignment before any of them is applied.

        Names, classes and houses are all looked up here, so a typo anywhere in
        the file is reported without half the roster having been reassigned.
        """
        cleaned = super().clean() or {}
        semester = cleaned.get("semester")
        if semester is None:
            return cleaned

        raw = self._raw_payload()
        if not raw.strip():
            raise forms.ValidationError("Paste some JSON or upload a file.")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise forms.ValidationError(f"That isn't valid JSON: {error}") from error

        entries = self._entries(payload, semester)
        students = {
            student.airtable_name: student
            for student in Student.objects.filter(semester=semester)
        }
        by_pk = {student.pk: student for student in students.values()}
        courses = {
            course.name: course for course in Course.objects.filter(semester=semester)
        }
        houses = {house.value: house for house in Student.House}

        assignments: list[Assignment] = []
        errors: list[str] = []
        seen: set[int] = set()
        for number, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                errors.append(f"Assignment {number}: expected an object.")
                continue

            student = by_pk.get(entry.get("id")) or students.get(
                str(entry.get("airtable_name", "")).strip()
            )
            if student is None:
                errors.append(
                    f"Assignment {number}: no student "
                    f"'{entry.get('airtable_name', entry.get('id'))}' in {semester}."
                )
                continue
            if student.pk in seen:
                errors.append(
                    f"Assignment {number}: {student.airtable_name} appears twice."
                )
                continue
            seen.add(student.pk)

            assigned: list[Course] | None = None
            if "courses" in entry:
                names = entry["courses"]
                if not isinstance(names, list):
                    errors.append(
                        f"Assignment {number}: 'courses' must be a list of names."
                    )
                    continue
                unknown = [str(name) for name in names if str(name) not in courses]
                if unknown:
                    errors.append(
                        f"Assignment {number} ({student.airtable_name}): "
                        f"no such class in {semester}: {', '.join(unknown)}."
                    )
                    continue
                assigned = [courses[str(name)] for name in names]

            house: Student.House | None = None
            if entry.get("house"):
                house = houses.get(str(entry["house"]))
                if house is None:
                    errors.append(
                        f"Assignment {number} ({student.airtable_name}): "
                        f"'{entry['house']}' is not a house. "
                        f"Choose from: {', '.join(houses)}."
                    )
                    continue

            if assigned is None and house is None:
                errors.append(
                    f"Assignment {number} ({student.airtable_name}): "
                    "nothing to do; give 'courses', 'house', or both."
                )
                continue
            assignments.append(Assignment(student, assigned, house))

        if errors:
            raise forms.ValidationError(errors)

        cleaned["assignments"] = assignments
        return cleaned

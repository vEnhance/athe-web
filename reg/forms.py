import json
from collections.abc import Iterable
from typing import Any, NamedTuple

from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.db import transaction

from courses.models import Course, Semester, Student
from home.models import StaffPhotoListing

from . import availability, questions
from .models import CoursePreference, StudentRegistration

#: Questions of the sorting ceremony, in the order they are asked.
QUIZ_FIELDS = (
    "quiz_challenge",
    "quiz_values",
    "quiz_compass",
    "quiz_day_off",
    "quiz_friend",
)


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
                    "on_hour": start.minute == 0,
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


class SearchableSelect(forms.Select):
    """A <select> the vendored Tom Select turns into a type-to-filter dropdown.

    Falls back to an ordinary dropdown if the script does not load, which is
    why the roster is a select at all: a hundred radio buttons is a hundred
    lines to scroll past to find your own name.
    """

    def __init__(
        self, attrs: dict[str, Any] | None = None, choices: Iterable[Any] = ()
    ) -> None:
        super().__init__({"data-tom-select": "", **(attrs or {})}, choices)


class SearchableSelectMultiple(forms.SelectMultiple):
    """The multi-select flavour of SearchableSelect."""

    def __init__(
        self, attrs: dict[str, Any] | None = None, choices: Iterable[Any] = ()
    ) -> None:
        super().__init__({"data-tom-select": "", **(attrs or {})}, choices)


class SubjectInterestWidget(forms.Widget):
    """A radio grid: one row per subject, one column per interest level.

    Four separate questions would say the same thing, but a grid lets students
    see how their answers compare and takes a quarter of the height.
    """

    template_name = "reg/widgets/subject_interest.html"

    def value_from_datadict(self, data: Any, files: Any, name: str) -> dict[str, str]:
        return {
            subject: data.get(f"{name}_{subject}", "")
            for subject, _ in questions.SUBJECTS
        }

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        answers = value or {}
        widget_id = (attrs or {}).get("id", name)
        context["widget"].update(
            levels=[label for _, label in questions.INTEREST_LEVELS],
            rows=[
                {
                    "label": subject_label,
                    "name": f"{name}_{subject}",
                    "cells": [
                        {
                            "value": level,
                            "id": f"{widget_id}_{subject}_{level}",
                            "label": f"{subject_label}: {level_label}",
                            "checked": answers.get(subject) == level,
                        }
                        for level, level_label in questions.INTEREST_LEVELS
                    ],
                }
                for subject, subject_label in questions.SUBJECTS
            ],
        )
        return context


class SubjectInterestField(forms.Field):
    """Collects the subject grid into ``{subject: interest level}``."""

    widget = SubjectInterestWidget

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("label", "How interested are you in each subject?")
        kwargs.setdefault(
            "help_text",
            "So we can make sure you get put in a class on a subject you're "
            "interested in.",
        )
        super().__init__(**kwargs)

    def clean(self, value: Any) -> dict[str, str]:
        answers = value or {}
        cleaned: dict[str, str] = {}
        missing: list[str] = []
        for subject, label in questions.SUBJECTS:
            if answers.get(subject) in questions.INTEREST_KEYS:
                cleaned[subject] = answers[subject]
            else:
                missing.append(label)

        if missing and self.required:
            raise forms.ValidationError(
                f"Please say how interested you are in {', '.join(missing)}."
            )
        return cleaned


class RegistrationStepForm(forms.ModelForm):  # type: ignore[type-arg]
    """One page of the student registration questionnaire.

    Every page saves on its own rather than being held in the session, so a
    student can stop halfway, come back on another device and carry on -- and
    so a half-finished registration is visible in the download rather than lost.
    """

    #: URL slug for this page, and the marker stored in completed_steps.
    slug: str
    #: Heading for this page, and its label in the progress bar.
    title: str
    #: Template rendering this page. (Not `template_name`, which Django uses
    #: for rendering the form itself.)
    page_template: str

    class Meta:
        model = StudentRegistration
        fields: list[str] = []

    def __init__(
        self,
        *args: Any,
        semester: Semester,
        # Only needed to save; a form built just to read its labels off can
        # leave it out.
        user: User | None = None,
        student: Student | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.semester = semester
        self.user = user
        self.claimed_student = student

    def save_step(self) -> StudentRegistration:
        """Store this page's answers and mark it done."""
        registration = super().save(commit=False)
        registration.mark_complete(self.slug)
        registration.save()
        return registration


class IdentityStepForm(RegistrationStepForm):
    """Page 1: which name on the roster you are, and how to reach you."""

    slug = "you"
    title = "About you"
    page_template = "reg/steps/you.html"

    taken_class_before = forms.TypedChoiceField(
        choices=(("yes", "Yes"), ("no", "No")),
        coerce=lambda value: value == "yes",
        widget=forms.RadioSelect,
        label="Have you taken an Athemath class before?",
    )

    class Meta(RegistrationStepForm.Meta):
        fields = ["email", "parent_email", "discord_username", "taken_class_before"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.claimed_student is not None:
            return
        # The whole roster is offered, claimed names included; picking a
        # claimed one is rejected by clean_student() below.
        self.fields["student"] = RosterField(
            queryset=Student.objects.filter(semester=self.semester),
            widget=SearchableSelect(
                attrs={"data-placeholder": "Start typing your name..."}
            ),
            empty_label="",
            label="Who are you?",
            help_text="Start typing to find your name on the roster.",
        )
        self.order_fields(["student", *self.Meta.fields])

    def clean_student(self) -> Student:
        student = self.cleaned_data["student"]
        if student.user is not None:
            raise forms.ValidationError(
                f"{student.airtable_name} has already been claimed by someone else. "
                "If you think this is a mistake, please contact us."
            )
        return student

    @transaction.atomic
    def save_step(self) -> StudentRegistration:
        """Bind the user to their Student, then store the page as usual."""
        assert self.user is not None
        student = self.claimed_student or self.cleaned_data["student"]
        if student.user != self.user:
            student.user = self.user
            student.save()
        self.instance.student = student
        return super().save_step()


class RosterField(forms.ModelChoiceField):  # type: ignore[type-arg]
    """The roster dropdown, labelled by Airtable name.

    Student.__str__ switches to the bound user's real name once a row is
    claimed, but students are looking for the name they applied under.
    """

    def label_from_instance(self, obj: Student) -> str:
        return obj.airtable_name


class CourseChoiceField(forms.ModelChoiceField):  # type: ignore[type-arg]
    """A dropdown of classes, labelled by name alone.

    Course.__str__ tacks the semester on, which is just noise on a form that
    only ever offers one semester's classes.
    """

    def label_from_instance(self, obj: Course) -> str:
        return obj.name


class CourseChoiceMultipleField(forms.ModelMultipleChoiceField):  # type: ignore[type-arg]
    """The multi-select flavour of CourseChoiceField."""

    def label_from_instance(self, obj: Course) -> str:
        return obj.name


class ClassPreferenceStepForm(RegistrationStepForm):
    """Page 2: what to teach this student, and at what level."""

    slug = "classes"
    title = "Class preferences"
    page_template = "reg/steps/classes.html"

    #: Choice fields, best first; the index is the rank that gets stored.
    CHOICE_FIELDS = ("first_choice", "second_choice", "third_choice")
    CHOICE_LABELS = ("First choice", "Second choice", "Third choice")

    subject_interest = SubjectInterestField()
    difficulty_levels = forms.MultipleChoiceField(
        choices=questions.DIFFICULTY_LEVELS,
        widget=forms.CheckboxSelectMultiple,
        label="Which level(s) of classes are you interested in taking?",
        help_text=questions.DIFFICULTY_HELP,
    )

    class Meta(RegistrationStepForm.Meta):
        fields = ["subject_interest", "difficulty_levels", "course_comments"]
        widgets = {"course_comments": forms.Textarea(attrs={"rows": 3})}
        labels = {"course_comments": "Anything else about your class preferences?"}
        help_texts = {"course_comments": ""}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        classes = Course.objects.filter(semester=self.semester, is_club=False).order_by(
            "name"
        )
        self.classes = list(classes)

        for index, (name, label) in enumerate(
            zip(self.CHOICE_FIELDS, self.CHOICE_LABELS, strict=True)
        ):
            self.fields[name] = CourseChoiceField(
                queryset=classes,
                # Only the first pick is compulsory; second and third are a
                # kindness to the matching, not a demand on the student.
                required=index == 0 and bool(self.classes),
                widget=SearchableSelect(attrs={"data-placeholder": "Pick a class..."}),
                empty_label="",
                label=label,
            )
        self.fields["avoid_courses"] = CourseChoiceMultipleField(
            queryset=classes,
            required=False,
            widget=SearchableSelectMultiple(
                attrs={"data-placeholder": "Usually none - leave empty if so"}
            ),
            label="Any classes you'd rather not take at all?",
            help_text="For instance because you have taken it before, or the "
            "difficulty is way outside your comfort zone.",
        )
        self.order_fields(
            [
                "subject_interest",
                "difficulty_levels",
                *self.CHOICE_FIELDS,
                "avoid_courses",
                "course_comments",
            ]
        )

        if self.instance.pk:
            self._load_preferences()

    def _load_preferences(self) -> None:
        """Show the picks already stored as CoursePreference rows."""
        avoided: list[int] = []
        for preference in CoursePreference.objects.filter(
            registration=self.instance
        ).select_related("course"):
            if preference.excluded:
                avoided.append(preference.course.pk)
            elif preference.rank and preference.rank <= len(self.CHOICE_FIELDS):
                self.initial[self.CHOICE_FIELDS[preference.rank - 1]] = (
                    preference.course.pk
                )
        self.initial["avoid_courses"] = avoided

    def picks(self) -> list[Course | None]:
        """The three choices in rank order, with gaps kept as None."""
        return [self.cleaned_data.get(name) for name in self.CHOICE_FIELDS]

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        picks = [cleaned.get(name) for name in self.CHOICE_FIELDS]
        chosen = [course for course in picks if course is not None]

        if len(set(chosen)) != len(chosen):
            raise forms.ValidationError(
                "Please pick a different class for each choice."
            )

        for earlier, later in zip(self.CHOICE_FIELDS, self.CHOICE_FIELDS[1:]):
            if cleaned.get(later) is not None and cleaned.get(earlier) is None:
                raise forms.ValidationError(
                    "Please fill your choices in order, starting from the first."
                )

        avoided = set(cleaned.get("avoid_courses") or ())
        clash = [course.name for course in chosen if course in avoided]
        if clash:
            raise forms.ValidationError(
                f"You picked {', '.join(clash)} as a choice and also as a class "
                "you'd rather not take."
            )
        return cleaned

    @transaction.atomic
    def save_step(self) -> StudentRegistration:
        registration = super().save_step()

        # Simpler to lay the picks down fresh than to diff them, and it keeps a
        # re-submission from leaving a dropped choice behind.
        CoursePreference.objects.filter(registration=registration).delete()
        chosen = [course for course in self.picks() if course is not None]
        CoursePreference.objects.bulk_create(
            [
                CoursePreference(registration=registration, course=course, rank=rank)
                for rank, course in enumerate(chosen, 1)
            ]
            + [
                CoursePreference(
                    registration=registration, course=course, excluded=True
                )
                for course in self.cleaned_data.get("avoid_courses") or ()
                if course not in chosen
            ]
        )
        return registration


class AvailabilityStepForm(RegistrationStepForm):
    """Page 3: when this student could actually attend a class."""

    slug = "availability"
    title = "Availability"
    page_template = "reg/steps/availability.html"

    availability = AvailabilityField()

    class Meta(RegistrationStepForm.Meta):
        fields = ["availability", "availability_comments"]
        widgets = {"availability_comments": forms.Textarea(attrs={"rows": 3})}
        labels = {"availability_comments": "Anything else about your availability?"}
        help_texts = {"availability_comments": ""}


class SortingStepForm(RegistrationStepForm):
    """Page 4: the sorting ceremony."""

    slug = "sorting"
    title = "Sorting ceremony"
    page_template = "reg/steps/sorting.html"

    class Meta(RegistrationStepForm.Meta):
        fields = [*QUIZ_FIELDS, "house_request"]
        widgets = {
            "house_request": forms.Textarea(attrs={"rows": 3}),
            **dict.fromkeys(QUIZ_FIELDS, forms.RadioSelect),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Every quiz question must be answered, so a model-supplied blank
        # choice would just be an unlabelled sixth radio button.
        for name in QUIZ_FIELDS:
            field = self.fields[name]
            field.choices = [  # type: ignore[attr-defined]
                choice
                for choice in field.choices  # type: ignore[attr-defined]
                if choice[0]
            ]

    def quiz_fields(self) -> list[Any]:
        """The sorting questions as bound fields, for the template to loop over."""
        return [self[name] for name in QUIZ_FIELDS]


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

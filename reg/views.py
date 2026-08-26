from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from atheweb.decorators import superuser_required
from courses.models import Course, Semester, Student
from home.models import StaffPhotoListing

from . import availability
from .forms import (
    Assignment,
    AssignmentUploadForm,
    LoginChoiceForm,
    StaffRegistrationForm,
    StaffSelectionForm,
    StudentQuestionnaireForm,
    StudentRegistrationForm,
)
from .models import (
    CoursePreference,
    StaffInviteLink,
    StudentInviteLink,
    StudentRegistration,
)


class StaffInviteView(View):
    """
    View for handling staff registration via invite links.

    This view implements a multi-step process:
    1. Verify the invite link is valid and not expired
    2. Let the user select which StaffPhotoListing they are
    3. If already registered, show error
    4. Otherwise, let them create a Django user account
    """

    invite: StaffInviteLink

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        """Resolve the invite once and turn away expired ones before GET/POST."""
        self.invite = get_object_or_404(StaffInviteLink, id=kwargs["invite_id"])
        if self.invite.is_expired():
            return render(request, "reg/invite_expired.html", {"invite": self.invite})
        return super().dispatch(request, *args, **kwargs)

    def _already_registered(
        self, request: HttpRequest, staff_listing: StaffPhotoListing
    ) -> HttpResponse:
        """Report that this listing has been claimed, abandoning the flow."""
        request.session.pop("staff_listing_id", None)
        assert staff_listing.user is not None
        return render(
            request,
            "reg/already_registered.html",
            {
                "staff_listing": staff_listing,
                "username": staff_listing.user.username,
            },
        )

    def _selected_listing(self, request: HttpRequest) -> StaffPhotoListing:
        """The listing chosen in step 1, from the session."""
        return get_object_or_404(
            StaffPhotoListing, id=request.session["staff_listing_id"]
        )

    def get(self, request: HttpRequest, invite_id: str) -> HttpResponse:
        """Display the staff selection form, or the registration form after it."""
        if "staff_listing_id" not in request.session:
            return render(
                request,
                "reg/select_staff.html",
                {"form": StaffSelectionForm(), "invite": self.invite},
            )

        staff_listing = self._selected_listing(request)
        if staff_listing.user is not None:
            return self._already_registered(request, staff_listing)

        return render(
            request,
            "reg/register.html",
            {
                "staff_listing": staff_listing,
                "form": StaffRegistrationForm(),
                "invite": self.invite,
            },
        )

    def post(self, request: HttpRequest, invite_id: str) -> HttpResponse:
        """Handle form submissions."""
        if "staff_listing_id" in request.session:
            return self._handle_registration(request)
        return self._handle_staff_selection(request)

    def _handle_staff_selection(self, request: HttpRequest) -> HttpResponse:
        """Handle the staff selection step."""
        form = StaffSelectionForm(request.POST)

        if form.is_valid():
            staff_listing = form.cleaned_data["staff_listing"]
            if staff_listing.user is not None:
                return self._already_registered(request, staff_listing)

            request.session["staff_listing_id"] = staff_listing.id
            return redirect("reg:add-staff", invite_id=self.invite.id)

        return render(
            request,
            "reg/select_staff.html",
            {"form": form, "invite": self.invite},
        )

    def _handle_registration(self, request: HttpRequest) -> HttpResponse:
        """Handle the registration step."""
        staff_listing = self._selected_listing(request)
        if staff_listing.user is not None:
            return self._already_registered(request, staff_listing)

        form = StaffRegistrationForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "reg/register.html",
                {
                    "staff_listing": staff_listing,
                    "form": form,
                    "invite": self.invite,
                },
            )

        with transaction.atomic():
            user = form.save(commit=False)
            user.is_staff = True
            user.save()

            staff_listing.user = user
            staff_listing.save()

            # Anyone listed as instructor of a course also leads it
            for course in Course.objects.filter(instructor=staff_listing):
                course.leaders.add(user)

        del request.session["staff_listing_id"]

        # Log the user in (specify backend since multiple are configured)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            request,
            f"Welcome, {user.get_full_name() or user.username}! "
            "Your staff account has been created successfully.",
        )
        return redirect("home:index")


class StudentInviteView(View):
    """
    View for handling student registration via invite links.

    This view implements a multi-step process:
    1. Verify the invite link is valid and not expired, and semester hasn't ended
    2. If not logged in, ask if they have an account (login vs create new)
    3. If creating new account, show registration form
    4. If logging in, redirect to login page with next parameter
    5. Once logged in, show the questionnaire: the student picks their name off
       the roster and answers everything the class matching needs
    6. Saving binds the user to the selected Student record

    A student who comes back to the link later gets the same questionnaire with
    their answers in it, so corrections don't have to go through Greta.
    """

    invite: StudentInviteLink

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        """Resolve the invite once and turn away closed ones before GET/POST."""
        self.invite = get_object_or_404(StudentInviteLink, id=kwargs["invite_id"])
        for closed, reason in (
            (self.invite.is_expired(), "expired"),
            (self.invite.is_semester_ended(), "semester_ended"),
        ):
            if closed:
                return render(
                    request,
                    "reg/student_invite_expired.html",
                    {"invite": self.invite, "reason": reason},
                )
        return super().dispatch(request, *args, **kwargs)

    def _existing_student(self, request: HttpRequest) -> Student | None:
        """The Student this user is already registered as for the semester."""
        return Student.objects.filter(
            user=request.user, semester=self.invite.semester
        ).first()

    def _questionnaire(
        self, request: HttpRequest, data: Any = None
    ) -> StudentQuestionnaireForm:
        """The questionnaire, in edit mode if this user already claimed a name."""
        student = self._existing_student(request)
        return StudentQuestionnaireForm(
            data,
            semester=self.invite.semester,
            student=student,
            instance=(
                StudentRegistration.objects.filter(student=student).first()
                if student
                else None
            ),
        )

    def _render_questionnaire(
        self, request: HttpRequest, form: StudentQuestionnaireForm
    ) -> HttpResponse:
        if (
            form.claimed_student is None
            and not Student.objects.filter(semester=self.invite.semester).exists()
        ):
            return render(
                request,
                "reg/no_students_available.html",
                {"semester": self.invite.semester},
            )
        return render(
            request,
            "reg/student_questionnaire.html",
            {
                "form": form,
                "invite": self.invite,
                "student": form.claimed_student,
                "editing": form.claimed_student is not None,
            },
        )

    def get(self, request: HttpRequest, invite_id: str) -> HttpResponse:
        """Display the appropriate step in the registration process."""
        if not request.user.is_authenticated:
            if "creating_new_account" in request.session:
                return render(
                    request,
                    "reg/student_register.html",
                    {"form": StudentRegistrationForm(), "invite": self.invite},
                )
            return render(
                request,
                "reg/login_choice.html",
                {"form": LoginChoiceForm(), "invite": self.invite},
            )

        return self._render_questionnaire(request, self._questionnaire(request))

    def post(self, request: HttpRequest, invite_id: str) -> HttpResponse:
        """Handle form submissions."""
        if request.user.is_authenticated:
            return self._handle_questionnaire(request)
        if "creating_new_account" in request.session:
            return self._handle_new_account_creation(request)
        return self._handle_login_choice(request)

    def _handle_login_choice(self, request: HttpRequest) -> HttpResponse:
        """Handle the login choice step (has account or create new)."""
        form = LoginChoiceForm(request.POST)

        if form.is_valid():
            if form.cleaned_data["has_account"] == "yes":
                return redirect(
                    f"{reverse('login')}?next={self.invite.get_absolute_url()}"
                )
            request.session["creating_new_account"] = True
            return redirect("reg:add-student", invite_id=self.invite.id)

        return render(
            request,
            "reg/login_choice.html",
            {"form": form, "invite": self.invite},
        )

    def _handle_new_account_creation(self, request: HttpRequest) -> HttpResponse:
        """Handle the new account creation step."""
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            del request.session["creating_new_account"]
            # Log the user in (specify backend since multiple are configured)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            # Back to the invite, now as a logged-in user
            return redirect("reg:add-student", invite_id=self.invite.id)

        return render(
            request,
            "reg/student_register.html",
            {"form": form, "invite": self.invite},
        )

    def _handle_questionnaire(self, request: HttpRequest) -> HttpResponse:
        """Claim the chosen name, if any, and store the student's answers."""
        form = self._questionnaire(request, request.POST)
        editing = form.claimed_student is not None
        if not form.is_valid():
            return self._render_questionnaire(request, form)

        assert isinstance(request.user, User)
        student = form.save_registration(request.user)
        if editing:
            messages.success(request, "Your registration has been updated. Thank you!")
        else:
            messages.success(
                request,
                f"Welcome! You are registered as {student.airtable_name} "
                f"for {self.invite.semester}. We'll be in touch with your classes "
                "once the schedule is worked out.",
            )
        return redirect("home:index")


def _course_json(course: Course) -> dict[str, Any]:
    """The bits of a class the matching problem cares about."""
    return {
        "id": course.pk,
        "name": course.name,
        "difficulty": course.difficulty,
        "instructor": str(course.instructor) if course.instructor else None,
        "regular_meeting_time": course.regular_meeting_time,
    }


def _registration_json(
    registration: StudentRegistration, preferences: list[CoursePreference]
) -> dict[str, Any]:
    """One student's answers, with course preferences split into two lists."""
    return {
        "email": registration.email,
        "parent_email": registration.parent_email,
        "discord_username": registration.discord_username,
        "taken_class_before": registration.taken_class_before,
        "course_ranking": [
            {"rank": pref.rank, "course_id": pref.course.pk, "course": pref.course.name}
            for pref in preferences
            if not pref.excluded
        ],
        "excluded_courses": [
            {"course_id": pref.course.pk, "course": pref.course.name}
            for pref in preferences
            if pref.excluded
        ],
        "course_comments": registration.course_comments,
        "availability": registration.availability,
        "availability_comments": registration.availability_comments,
        "quiz": registration.quiz_answers(),
        "house_request": registration.house_request,
        "submitted_at": registration.created_at.isoformat(),
        "updated_at": registration.updated_at.isoformat(),
    }


def _responses_payload(semester: Semester) -> dict[str, Any]:
    """Everything needed to compute the matching, in one JSON-ready dict.

    Students who have not filled the questionnaire in are listed too, with a
    null registration, so it is obvious from the download alone who is missing.
    """
    students = Student.objects.filter(semester=semester).select_related("user")
    registrations = {
        registration.student.pk: registration
        for registration in StudentRegistration.objects.filter(
            student__semester=semester
        ).select_related("student")
    }
    preferences: defaultdict[int, list[CoursePreference]] = defaultdict(list)
    for preference in CoursePreference.objects.filter(
        registration__student__semester=semester
    ).select_related("course", "registration"):
        preferences[preference.registration.pk].append(preference)

    # The questionnaire itself supplies the sorting-quiz legend, so whatever
    # reads this download sees the questions exactly as students were asked.
    questions = StudentQuestionnaireForm(semester=semester)
    return {
        "semester": {
            "name": semester.name,
            "slug": semester.slug,
            "start_date": semester.start_date.isoformat(),
            "end_date": semester.end_date.isoformat(),
        },
        "generated_at": timezone.now().isoformat(),
        "courses": [
            _course_json(course)
            for course in Course.objects.filter(semester=semester, is_club=False)
        ],
        "availability_slots": [
            {"key": key, "label": label} for key, label in availability.slot_choices()
        ],
        "houses": [
            {"value": house.value, "label": house.label} for house in Student.House
        ],
        "quiz_questions": {
            name: {
                "question": str(questions.fields[name].label),
                "choices": dict(questions.fields[name].choices),  # type: ignore[attr-defined]
            }
            for name in StudentQuestionnaireForm.QUIZ_FIELDS
        },
        "students": [
            {
                "id": student.pk,
                "airtable_name": student.airtable_name,
                "house": student.house,
                "user": (
                    {
                        "username": student.user.username,
                        "full_name": student.user.get_full_name(),
                        "email": student.user.email,
                    }
                    if student.user
                    else None
                ),
                "registration": (
                    _registration_json(
                        registrations[student.pk],
                        preferences[registrations[student.pk].pk],
                    )
                    if student.pk in registrations
                    else None
                ),
            }
            for student in students
        ],
    }


@superuser_required()
def student_responses(request: HttpRequest, slug: str) -> HttpResponse:
    """Download every questionnaire response for a semester as JSON."""
    semester = get_object_or_404(Semester, slug=slug)
    response = JsonResponse(
        _responses_payload(semester), json_dumps_params={"indent": 2}
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{semester.slug}-responses.json"'
    )
    return response


@transaction.atomic
def _apply_assignments(
    semester: Semester, assignments: list[Assignment]
) -> list[dict[str, Any]]:
    """Enroll students in their computed classes and sort them into houses."""
    classes = Course.objects.filter(semester=semester, is_club=False)
    enrollment = Course.students.through

    # Replacing enrollments only clears classes; clubs a student joined on
    # their own are none of the matching's business.
    rostered = [entry for entry in assignments if entry.courses is not None]
    if rostered:
        enrollment.objects.filter(
            student__in=[entry.student for entry in rostered], course__in=classes
        ).delete()
        enrollment.objects.bulk_create(
            (
                enrollment(student_id=entry.student.pk, course_id=course.pk)
                for entry in rostered
                for course in entry.courses or ()
            ),
            ignore_conflicts=True,
        )

    sorted_students = []
    for entry in assignments:
        if entry.house is not None:
            entry.student.house = entry.house
            sorted_students.append(entry.student)
    Student.objects.bulk_update(sorted_students, ["house"])

    return [
        {
            "student": entry.student.airtable_name,
            "courses": [course.name for course in entry.courses or ()],
            "courses_changed": entry.courses is not None,
            "house": entry.house.label if entry.house else "",
        }
        for entry in assignments
    ]


@superuser_required()
def upload_assignments(request: HttpRequest) -> HttpResponse:
    """Apply a computed matching of students to classes and houses."""
    form = AssignmentUploadForm(request.POST or None, request.FILES or None)
    applied = None

    if request.method == "POST" and form.is_valid():
        semester = form.cleaned_data["semester"]
        applied = _apply_assignments(semester, form.cleaned_data["assignments"])
        messages.success(request, f"Applied {len(applied)} assignments for {semester}.")

    return render(
        request,
        "reg/upload_assignments.html",
        {
            "form": form,
            "applied": applied,
            "semesters": Semester.objects.all(),
        },
    )

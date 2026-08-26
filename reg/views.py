from typing import Any

from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from courses.models import Course, Student
from home.models import StaffPhotoListing

from .forms import (
    LoginChoiceForm,
    StaffRegistrationForm,
    StaffSelectionForm,
    StudentRegistrationForm,
    StudentSelectionForm,
)
from .models import StaffInviteLink, StudentInviteLink


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
    5. Once logged in, check if they already have a Student for this semester
    6. If not, let them select which Student record they are from the roster
    7. Link the user to the selected Student record
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

    def _already_registered(
        self, request: HttpRequest, student: Student
    ) -> HttpResponse:
        return render(
            request,
            "reg/student_already_registered.html",
            {"student": student, "semester": self.invite.semester},
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

        existing_student = self._existing_student(request)
        if existing_student:
            return self._already_registered(request, existing_student)

        form = StudentSelectionForm(semester=self.invite.semester)
        if not form.fields["student"].queryset.exists():  # type: ignore[attr-defined]
            return render(
                request,
                "reg/no_students_available.html",
                {"semester": self.invite.semester},
            )

        return render(
            request,
            "reg/select_student.html",
            {"form": form, "invite": self.invite},
        )

    def post(self, request: HttpRequest, invite_id: str) -> HttpResponse:
        """Handle form submissions."""
        if request.user.is_authenticated:
            return self._handle_student_selection(request)
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

    def _handle_student_selection(self, request: HttpRequest) -> HttpResponse:
        """Handle the student selection step."""
        existing_student = self._existing_student(request)
        if existing_student:
            return self._already_registered(request, existing_student)

        form = StudentSelectionForm(semester=self.invite.semester, data=request.POST)
        if form.is_valid():
            student = form.cleaned_data["student"]

            # The roster lists everyone, so the name may already be claimed
            if student.user is not None:
                return render(
                    request,
                    "reg/student_already_taken.html",
                    {"student": student},
                )

            student.user = request.user
            student.save()
            messages.success(
                request,
                f"Welcome! You have been successfully registered as "
                f"{student.airtable_name} for {self.invite.semester}.",
            )
            return redirect("home:index")

        return render(
            request,
            "reg/select_student.html",
            {"form": form, "invite": self.invite},
        )

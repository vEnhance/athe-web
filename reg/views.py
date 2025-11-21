from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
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

    def get(self, request, invite_id):  # type: ignore
        """Display the staff selection form."""
        invite = get_object_or_404(StaffInviteLink, id=invite_id)

        # Check if the invite link has expired
        if invite.is_expired():
            return render(
                request,
                "reg/invite_expired.html",
                {"invite": invite},
            )

        # Check if we're at step 2 (registration)
        if "staff_listing_id" in request.session:
            staff_listing_id = request.session["staff_listing_id"]
            staff_listing = get_object_or_404(StaffPhotoListing, id=staff_listing_id)

            # Verify this listing doesn't have a user
            if staff_listing.user is not None:
                # Clear the session and show error
                del request.session["staff_listing_id"]
                return render(
                    request,
                    "reg/already_registered.html",
                    {
                        "staff_listing": staff_listing,
                        "username": staff_listing.user.username,
                    },
                )

            # Show registration form
            registration_form = StaffRegistrationForm()
            return render(
                request,
                "reg/register.html",
                {
                    "staff_listing": staff_listing,
                    "form": registration_form,
                    "invite": invite,
                },
            )

        # Show staff selection form
        selection_form = StaffSelectionForm()
        return render(
            request,
            "reg/select_staff.html",
            {
                "form": selection_form,
                "invite": invite,
            },
        )

    def post(self, request, invite_id):  # type: ignore
        """Handle form submissions."""
        invite = get_object_or_404(StaffInviteLink, id=invite_id)

        # Check if the invite link has expired
        if invite.is_expired():
            return render(
                request,
                "reg/invite_expired.html",
                {"invite": invite},
            )

        # Check if we're at step 2 (registration)
        if "staff_listing_id" in request.session:
            return self._handle_registration(request, invite)
        else:
            return self._handle_staff_selection(request, invite)

    def _handle_staff_selection(self, request, invite):  # type: ignore
        """Handle the staff selection step."""
        form = StaffSelectionForm(request.POST)

        if form.is_valid():
            staff_listing = form.cleaned_data["staff_listing"]

            # Check if this staff listing already has a user
            if staff_listing.user is not None:
                return render(
                    request,
                    "reg/already_registered.html",
                    {
                        "staff_listing": staff_listing,
                        "username": staff_listing.user.username,
                    },
                )

            # Store the selected staff listing in the session
            request.session["staff_listing_id"] = staff_listing.id
            return redirect("reg:add-staff", invite_id=invite.id)

        # Form is invalid, show errors
        return render(
            request,
            "reg/select_staff.html",
            {
                "form": form,
                "invite": invite,
            },
        )

    def _handle_registration(self, request, invite):  # type: ignore
        """Handle the registration step."""
        staff_listing_id = request.session["staff_listing_id"]
        staff_listing = get_object_or_404(StaffPhotoListing, id=staff_listing_id)

        # Double-check the listing doesn't have a user
        if staff_listing.user is not None:
            del request.session["staff_listing_id"]
            return render(
                request,
                "reg/already_registered.html",
                {
                    "staff_listing": staff_listing,
                    "username": staff_listing.user.username,
                },
            )

        form = StaffRegistrationForm(request.POST)

        if form.is_valid():
            # Create the user account atomically
            with transaction.atomic():
                # Create the user
                user = form.save(commit=False)
                user.is_staff = True
                user.save()

                # Link the user to the staff listing
                staff_listing.user = user
                staff_listing.save()

                # Add the user as a leader to any courses where they are the instructor
                courses = Course.objects.filter(instructor=staff_listing)
                for course in courses:
                    course.leaders.add(user)

            # Clear the session
            del request.session["staff_listing_id"]

            # Log the user in (specify backend since multiple are configured)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Show success message
            messages.success(
                request,
                f"Welcome, {user.get_full_name() or user.username}! Your staff account has been created successfully.",
            )

            return redirect("home:index")

        # Form is invalid, show errors
        return render(
            request,
            "reg/register.html",
            {
                "staff_listing": staff_listing,
                "form": form,
                "invite": invite,
            },
        )


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

    def get(self, request, invite_id):  # type: ignore
        """Display the appropriate step in the registration process."""
        invite = get_object_or_404(StudentInviteLink, id=invite_id)

        # Check if the invite link has expired
        if invite.is_expired():
            return render(
                request,
                "reg/student_invite_expired.html",
                {"invite": invite, "reason": "expired"},
            )

        # Check if the semester has ended
        if invite.is_semester_ended():
            return render(
                request,
                "reg/student_invite_expired.html",
                {"invite": invite, "reason": "semester_ended"},
            )

        # Step 1: If user is not logged in, ask if they have an account
        if not request.user.is_authenticated:
            # Check if we're at the registration step
            if "creating_new_account" in request.session:
                registration_form = StudentRegistrationForm()
                return render(
                    request,
                    "reg/student_register.html",
                    {
                        "form": registration_form,
                        "invite": invite,
                    },
                )

            # Show login choice form
            login_choice_form = LoginChoiceForm()
            return render(
                request,
                "reg/login_choice.html",
                {
                    "form": login_choice_form,
                    "invite": invite,
                },
            )

        # User is logged in at this point
        # Check if user already has a Student for this semester
        existing_student = Student.objects.filter(
            user=request.user, semester=invite.semester
        ).first()

        if existing_student:
            return render(
                request,
                "reg/student_already_registered.html",
                {
                    "student": existing_student,
                    "semester": invite.semester,
                },
            )

        # Check if we have a selected student in session
        if "student_id" in request.session:
            student_id = request.session["student_id"]
            student = get_object_or_404(Student, id=student_id)

            # Verify this student is from the correct semester and doesn't have a user
            if student.semester != invite.semester:
                del request.session["student_id"]
                messages.error(request, "Invalid student selection.")
                return redirect("reg:add-student", invite_id=invite.id)

            if student.user is not None:
                # Someone else took this student
                del request.session["student_id"]
                return render(
                    request,
                    "reg/student_already_taken.html",
                    {
                        "student": student,
                    },
                )

            # Show confirmation (this shouldn't happen in normal flow, but just in case)
            return redirect("reg:add-student", invite_id=invite.id)

        # Show student selection form
        selection_form = StudentSelectionForm(semester=invite.semester)

        # Check if there are any available students
        if not selection_form.fields["student"].queryset.exists():  # type: ignore
            return render(
                request,
                "reg/no_students_available.html",
                {
                    "semester": invite.semester,
                },
            )

        return render(
            request,
            "reg/select_student.html",
            {
                "form": selection_form,
                "invite": invite,
            },
        )

    def post(self, request, invite_id):  # type: ignore
        """Handle form submissions."""
        invite = get_object_or_404(StudentInviteLink, id=invite_id)

        # Check if the invite link has expired
        if invite.is_expired():
            return render(
                request,
                "reg/student_invite_expired.html",
                {"invite": invite, "reason": "expired"},
            )

        # Check if the semester has ended
        if invite.is_semester_ended():
            return render(
                request,
                "reg/student_invite_expired.html",
                {"invite": invite, "reason": "semester_ended"},
            )

        # Handle login choice (when not logged in)
        if not request.user.is_authenticated:
            # Check if we're at the registration step
            if "creating_new_account" in request.session:
                return self._handle_new_account_creation(request, invite)
            else:
                return self._handle_login_choice(request, invite)

        # User is logged in - handle student selection
        return self._handle_student_selection(request, invite)

    def _handle_login_choice(self, request, invite):  # type: ignore
        """Handle the login choice step (has account or create new)."""
        form = LoginChoiceForm(request.POST)

        if form.is_valid():
            has_account = form.cleaned_data["has_account"]

            if has_account == "yes":
                # Redirect to login page with next parameter
                login_url = reverse("account_login")
                next_url = invite.get_absolute_url()
                return redirect(f"{login_url}?next={next_url}")
            else:
                # Show registration form
                request.session["creating_new_account"] = True
                return redirect("reg:add-student", invite_id=invite.id)

        # Form is invalid, show errors
        return render(
            request,
            "reg/login_choice.html",
            {
                "form": form,
                "invite": invite,
            },
        )

    def _handle_new_account_creation(self, request, invite):  # type: ignore
        """Handle the new account creation step."""
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            # Create the user account
            user = form.save()

            # Clear the session flag
            del request.session["creating_new_account"]

            # Log the user in (specify backend since multiple are configured)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Redirect back to the invite link (now as logged in user)
            return redirect("reg:add-student", invite_id=invite.id)

        # Form is invalid, show errors
        return render(
            request,
            "reg/student_register.html",
            {
                "form": form,
                "invite": invite,
            },
        )

    def _handle_student_selection(self, request, invite):  # type: ignore
        """Handle the student selection step."""
        # Check if user already has a Student for this semester
        existing_student = Student.objects.filter(
            user=request.user, semester=invite.semester
        ).first()

        if existing_student:
            return render(
                request,
                "reg/student_already_registered.html",
                {
                    "student": existing_student,
                    "semester": invite.semester,
                },
            )

        # Check if a student was posted and if it's already taken
        # We need to do this before form validation because the form queryset
        # excludes students with users, so validation would fail
        if "student" in request.POST:
            try:
                student_id = int(request.POST["student"])
                student = Student.objects.filter(
                    id=student_id, semester=invite.semester
                ).first()
                if student and student.user is not None:
                    return render(
                        request,
                        "reg/student_already_taken.html",
                        {
                            "student": student,
                        },
                    )
            except (ValueError, TypeError):
                # Invalid student_id, let form validation handle it
                pass

        form = StudentSelectionForm(invite.semester, request.POST)

        if form.is_valid():
            student = form.cleaned_data["student"]

            # Double-check the student doesn't have a user yet
            if student.user is not None:
                return render(
                    request,
                    "reg/student_already_taken.html",
                    {
                        "student": student,
                    },
                )

            # Link the user to the student atomically
            with transaction.atomic():
                student.user = request.user
                student.save()

            # Show success message
            messages.success(
                request,
                f"Welcome! You have been successfully registered as {student.airtable_name} for {invite.semester}.",
            )

            return redirect("home:index")

        # Form is invalid, show errors
        return render(
            request,
            "reg/select_student.html",
            {
                "form": form,
                "invite": invite,
            },
        )

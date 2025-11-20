from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from courses.models import Course
from home.models import StaffPhotoListing

from .forms import StaffRegistrationForm, StaffSelectionForm
from .models import StaffInviteLink


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

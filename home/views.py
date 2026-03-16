from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView, UpdateView


from .models import ApplyPSet, StaffPhotoListing


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information."""

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ProfileSettingsView(LoginRequiredMixin, View):
    """View for users to update their profile settings."""

    template_name = "home/profile_settings.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the profile settings forms."""
        user = cast(User, request.user)
        profile_form = UserProfileForm(instance=user)
        password_form = PasswordChangeForm(user)
        context = {
            "profile_form": profile_form,
            "password_form": password_form,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle form submissions for profile or password updates."""
        user = cast(User, request.user)
        if "update_profile" in request.POST:
            profile_form = UserProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile has been updated successfully.")
                return redirect("home:profile_settings")
            password_form = PasswordChangeForm(user)
        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                saved_user = password_form.save()
                update_session_auth_hash(request, saved_user)
                messages.success(
                    request, "Your password has been changed successfully."
                )
                return redirect("home:profile_settings")
            profile_form = UserProfileForm(instance=user)
        else:
            profile_form = UserProfileForm(instance=user)
            password_form = PasswordChangeForm(user)

        context = {
            "profile_form": profile_form,
            "password_form": password_form,
        }
        return render(request, self.template_name, context)


class StaffView(TemplateView):
    """Staff page."""

    template_name = "home/staff.html"

    def get_context_data(self, **kwargs):
        """Add staff listings grouped by category."""
        context = super().get_context_data(**kwargs)
        context["board"] = StaffPhotoListing.objects.filter(category="board")
        context["instructor"] = StaffPhotoListing.objects.filter(category="instructor")
        context["ta"] = StaffPhotoListing.objects.filter(category="ta")
        return context


class PastStaffView(TemplateView):
    """Staff page."""

    template_name = "home/past_staff.html"

    def get_context_data(self, **kwargs):
        """Add staff listings grouped by category."""
        context = super().get_context_data(**kwargs)
        context["xstaff"] = StaffPhotoListing.objects.filter(category="xstaff")
        return context


class StaffDetailView(DetailView):
    """Staff member detail page."""

    model = StaffPhotoListing
    template_name = "home/staff_detail.html"
    context_object_name = "staff_member"
    object: StaffPhotoListing

    def get_context_data(self, **kwargs):
        """Add courses taught by this staff member."""
        context = super().get_context_data(**kwargs)
        context["courses_taught"] = self.object.courses.select_related("semester").all()  # type: ignore[attr-defined]
        return context


class StaffPhotoUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for staff members to update their own listing."""

    model = StaffPhotoListing
    fields = [
        "display_name",
        "biography",
        "photo",
        "website",
        "email",
        "instagram_username",
        "discord_username",
        "github_username",
    ]
    template_name = "home/staff_edit.html"
    success_url = reverse_lazy("home:staff")

    def test_func(self) -> bool:
        """Only allow the user to edit their own listing."""
        obj = self.get_object()
        return obj.user == self.request.user

    def get_object(self, queryset=None):
        """Get the staff listing for the current user."""
        return get_object_or_404(StaffPhotoListing, user=self.request.user)


class ApplyView(TemplateView):
    """Apply to be a student page."""

    template_name = "home/apply.html"

    def get_context_data(self, **kwargs):
        """Add active psets or closed message."""
        context = super().get_context_data(**kwargs)

        # Get all active problem sets
        active_psets = ApplyPSet.objects.filter(status="active")

        if active_psets.exists():
            context["active_psets"] = active_psets
        else:
            context["most_recent_pset"] = ApplyPSet.objects.filter(
                status="completed"
            ).first()

        return context


class PastPsetsView(ListView):
    """Past Problem Sets listing page."""

    model = ApplyPSet
    template_name = "home/past_psets.html"
    context_object_name = "psets"

    def get_queryset(self):
        """Return only completed problem sets in reverse chronological order."""
        return ApplyPSet.objects.filter(status="completed").order_by("-deadline")


class ManualView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Manual page for superusers."""

    def test_func(self) -> bool:
        return isinstance(self.request.user, User) and self.request.user.is_superuser

    template_name = "home/manual.html"

from datetime import date
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from courses.models import Semester, Student

from .forms import YearbookEntryForm
from .models import YearbookEntry


class StudentOwnerMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to verify user owns the student and semester hasn't ended."""

    def get_student(self) -> Student:
        """Get the student object. Must be implemented by subclasses."""
        raise NotImplementedError

    def test_func(self) -> bool:
        if not self.request.user.is_authenticated:  # type: ignore[union-attr]
            return False
        student = self.get_student()
        # Check user owns the student
        if student.user != self.request.user:  # type: ignore[union-attr]
            return False
        # Check semester hasn't ended
        if date.today() > student.semester.end_date:
            return False
        return True


class YearbookEntryCreateView(StudentOwnerMixin, CreateView):
    """Create a new yearbook entry for a student."""

    model = YearbookEntry
    form_class = YearbookEntryForm
    template_name = "yearbook/yearbookentry_form.html"

    def get_student(self) -> Student:
        if not hasattr(self, "_student"):
            self._student = get_object_or_404(
                Student, pk=self.kwargs["student_pk"], user=self.request.user
            )
        return self._student

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        # Check if student already has an entry
        student = get_object_or_404(Student, pk=self.kwargs["student_pk"])
        try:
            entry = student.yearbook_entry  # type: ignore[attr-defined]
            # Redirect to edit view if entry already exists
            return redirect("yearbook:edit", pk=entry.pk)
        except YearbookEntry.DoesNotExist:
            pass
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: YearbookEntryForm) -> HttpResponseBase:
        form.instance.student = self.get_student()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse(
            "yearbook:entry_list",
            kwargs={"slug": self.get_student().semester.slug},
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.get_student()
        context["is_create"] = True
        return context


class YearbookEntryUpdateView(StudentOwnerMixin, UpdateView):
    """Update an existing yearbook entry."""

    model = YearbookEntry
    form_class = YearbookEntryForm
    template_name = "yearbook/yearbookentry_form.html"

    def get_student(self) -> Student:
        return self.get_object().student

    def get_queryset(self):
        # Only allow editing entries owned by the current user
        return YearbookEntry.objects.filter(student__user=self.request.user)

    def get_success_url(self) -> str:
        return reverse(
            "yearbook:entry_list",
            kwargs={"slug": self.get_object().student.semester.slug},
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["student"] = self.get_student()
        context["is_create"] = False
        return context


class YearbookEntryListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List all yearbook entries for a semester."""

    model = YearbookEntry
    template_name = "yearbook/yearbook_entry_list.html"
    context_object_name = "entries"

    def get_semester(self) -> Semester:
        if not hasattr(self, "_semester"):
            self._semester = get_object_or_404(Semester, slug=self.kwargs["slug"])
        return self._semester

    def test_func(self) -> bool:
        if not self.request.user.is_authenticated:  # type: ignore[union-attr]
            return False
        assert isinstance(self.request.user, User)
        semester = self.get_semester()

        # Staff can view any semester
        if self.request.user.is_staff:
            return True

        # Users with a student in this semester can view
        return Student.objects.filter(
            user=self.request.user, semester=semester
        ).exists()

    def get_queryset(self):
        semester = self.get_semester()
        return (
            YearbookEntry.objects.filter(student__semester=semester)
            .select_related("student", "student__semester")
            .order_by("student__house", "display_name")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        semester = self.get_semester()
        context["semester"] = semester

        # Get other semesters for navigation
        context["other_semesters"] = Semester.objects.exclude(pk=semester.pk).order_by(
            "-end_date"
        )

        # Get the current user's student for this semester (if any)
        if self.request.user.is_authenticated:  # type: ignore[union-attr]
            user_student = Student.objects.filter(
                user=self.request.user, semester=semester
            ).first()
            context["user_student"] = user_student

            # Check if user can create/edit their entry
            if user_student:
                context["can_edit"] = date.today() <= semester.end_date
                try:
                    context["user_entry"] = user_student.yearbook_entry  # type: ignore[attr-defined]
                    context["has_entry"] = True
                except YearbookEntry.DoesNotExist:
                    context["has_entry"] = False

        return context


class SemesterListView(LoginRequiredMixin, ListView):
    """List all semesters with links to their yearbook entries."""

    model = Semester
    template_name = "yearbook/semester_list.html"
    context_object_name = "semesters"

    def get_queryset(self):
        return Semester.objects.order_by("-end_date")


class YearbookIndexView(LoginRequiredMixin, ListView):
    """Redirect to the most recent accessible semester or semester list."""

    model = Semester

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        user = request.user
        assert isinstance(user, User)

        # Get the most recent semester
        most_recent = Semester.objects.order_by("-end_date").first()

        if most_recent:
            # Check if user has access to the most recent semester
            if (
                user.is_staff
                or Student.objects.filter(user=user, semester=most_recent).exists()
            ):
                return redirect("yearbook:entry_list", slug=most_recent.slug)

        # Otherwise, redirect to semester list
        return redirect("yearbook:semester_list")

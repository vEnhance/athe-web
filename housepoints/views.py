from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from courses.models import Semester, Student
from housepoints.models import Award


@login_required
def leaderboard(request: HttpRequest, slug: str | None = None) -> HttpResponse:
    """Show the house points leaderboard for a semester."""
    # Get semester (default to most recent active or latest)
    if slug:
        semester = get_object_or_404(Semester, slug=slug)
    else:
        semester = Semester.objects.order_by("-start_date").first()
        if not semester:
            return render(
                request,
                "housepoints/leaderboard.html",
                {"semester": None, "leaderboard_data": []},
            )

    # Check if user has access (staff or enrolled student)
    assert isinstance(request.user, User)
    if not request.user.is_staff:
        has_access = Student.objects.filter(
            user=request.user, semester=semester
        ).exists()
        if not has_access:
            messages.error(
                request, "You don't have access to this semester's leaderboard."
            )
            return redirect("home:index")

    # Calculate total points per house, respecting freeze date
    awards_query = Award.objects.filter(semester=semester)

    # Apply freeze date if set
    if semester.house_points_freeze_date:
        awards_query = awards_query.filter(
            awarded_at__lte=semester.house_points_freeze_date
        )

    # Aggregate points by house
    house_totals = (
        awards_query.values("house")
        .annotate(total_points=Sum("points"))
        .order_by("-total_points")
    )

    # Create leaderboard data with house display names
    leaderboard_data = []
    for entry in house_totals:
        if entry["house"]:  # Skip empty house entries
            leaderboard_data.append(
                {
                    "house": entry["house"],
                    "house_display": dict(Student.House.choices).get(
                        entry["house"], entry["house"]
                    ),
                    "total_points": entry["total_points"] or 0,
                }
            )

    # Add houses with 0 points that aren't in the results
    houses_in_leaderboard = {entry["house"] for entry in leaderboard_data}
    for house_code, house_name in Student.House.choices:
        if house_code not in houses_in_leaderboard:
            leaderboard_data.append(
                {
                    "house": house_code,
                    "house_display": house_name,
                    "total_points": 0,
                }
            )

    # Sort by points descending
    leaderboard_data.sort(key=lambda x: -x["total_points"])

    # Get all semesters for navigation
    semesters = Semester.objects.order_by("-start_date")

    return render(
        request,
        "housepoints/leaderboard.html",
        {
            "semester": semester,
            "leaderboard_data": leaderboard_data,
            "semesters": semesters,
            "is_frozen": semester.house_points_freeze_date is not None,
            "freeze_date": semester.house_points_freeze_date,
        },
    )


class BulkAwardForm(forms.Form):
    """Form for bulk awarding points to multiple students."""

    award_type = forms.ChoiceField(
        choices=Award.AwardType.choices, help_text="Type of award to give"
    )
    usernames = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one username per line"}
        ),
        help_text="Enter usernames, one per line",
    )
    points = forms.IntegerField(
        required=False,
        help_text="Override default points (leave blank for default)",
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Optional description for all awards",
    )

    def clean_usernames(self) -> list[str]:
        """Parse usernames from textarea."""
        usernames_text = self.cleaned_data["usernames"]
        usernames = [u.strip() for u in usernames_text.strip().split("\n") if u.strip()]
        return usernames


class BulkAwardView(UserPassesTestMixin, View):
    """Staff-only view for bulk creating awards."""

    def test_func(self) -> bool:
        """Only staff can access this view."""
        return self.request.user.is_staff  # type: ignore[attr-defined]

    def _get_current_semester(self) -> Semester:
        """Get the current active semester based on today's date."""
        from django.utils import timezone

        today = timezone.now().date()
        current_semesters = Semester.objects.filter(
            start_date__lte=today, end_date__gte=today
        )

        count = current_semesters.count()
        if count == 0:
            raise ValueError("No active semester found for the current date.")
        if count > 1:
            raise ValueError(
                "Multiple active semesters found for the current date. "
                "Please ensure semester dates do not overlap."
            )

        return current_semesters.first()  # type: ignore[return-value]

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the bulk award form."""
        try:
            semester = self._get_current_semester()
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("home:index")

        form = BulkAwardForm()

        # Get students for the current semester only
        students_data = self._get_students_data(semester)

        return render(
            request,
            "housepoints/bulk_award.html",
            {
                "form": form,
                "results": None,
                "students_json": students_data,
                "semester": semester,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        """Process bulk award creation."""
        try:
            semester = self._get_current_semester()
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("home:index")

        form = BulkAwardForm(request.POST)
        results = {"success": [], "errors": []}

        if form.is_valid():
            award_type = form.cleaned_data["award_type"]
            usernames = form.cleaned_data["usernames"]
            points = form.cleaned_data["points"]
            description = form.cleaned_data["description"]

            # Use default points if not specified
            if points is None:
                points = Award.DEFAULT_POINTS.get(award_type, 0)

            for username in usernames:
                try:
                    # Find the student record
                    student = Student.objects.select_related("user").get(
                        user__username=username, semester=semester
                    )

                    if not student.house:
                        results["errors"].append(f"{username}: No house assigned")
                        continue

                    # Create the award
                    Award.objects.create(
                        semester=semester,
                        student=student,
                        house=student.house,
                        award_type=award_type,
                        points=points,
                        description=description,
                        awarded_by=request.user,
                    )
                    results["success"].append(
                        f"{username}: +{points} pts ({student.get_house_display()})"  # type: ignore[attr-defined]
                    )
                except Student.DoesNotExist:
                    results["errors"].append(
                        f"{username}: Not enrolled in {semester.name}"
                    )
                except Exception as e:
                    results["errors"].append(f"{username}: {str(e)}")

            if results["success"]:
                messages.success(
                    request, f"Successfully created {len(results['success'])} awards."
                )
            if results["errors"]:
                messages.warning(
                    request, f"{len(results['errors'])} awards failed to create."
                )

        # Get students data for re-rendering
        students_data = self._get_students_data(semester)

        return render(
            request,
            "housepoints/bulk_award.html",
            {
                "form": form,
                "results": results,
                "students_json": students_data,
                "semester": semester,
            },
        )

    def _get_students_data(self, semester: Semester) -> str:
        """Get JSON-encoded student data for autocomplete."""
        import json

        students = (
            Student.objects.filter(semester=semester)
            .select_related("user")
            .order_by("user__username")
        )

        students_list = []
        for student in students:
            full_name = student.user.get_full_name()
            if full_name:
                display_name = f"{full_name} ({student.user.username})"
            else:
                display_name = student.user.username

            if student.house:
                house_display = student.get_house_display()  # type: ignore[attr-defined]
                display_name += f" - {house_display}"

            students_list.append(
                {
                    "username": student.user.username,
                    "display": display_name,
                    # Add searchable fields
                    "first_name": student.user.first_name.lower(),
                    "last_name": student.user.last_name.lower(),
                    "email": student.user.email.lower(),
                }
            )

        return json.dumps(students_list)


@login_required
def my_awards(request: HttpRequest) -> HttpResponse:
    """Show all awards earned by the current user across semesters."""
    # Get all student records for this user
    student_records = Student.objects.filter(user=request.user).select_related(
        "semester"
    )

    # Get all awards for these students
    awards = (
        Award.objects.filter(student__in=student_records)
        .select_related("student__semester")
        .order_by("-awarded_at")
    )

    # Calculate total points per semester
    semester_totals = {}
    for student in student_records:
        total = Award.objects.filter(student=student).aggregate(total=Sum("points"))[
            "total"
        ]
        semester_totals[student.semester.id] = {  # type: ignore[attr-defined]
            "semester": student.semester,
            "house": student.get_house_display() if student.house else "Unassigned",  # type: ignore[attr-defined]
            "total": total or 0,
        }

    return render(
        request,
        "housepoints/my_awards.html",
        {
            "awards": awards,
            "semester_totals": list(semester_totals.values()),
        },
    )

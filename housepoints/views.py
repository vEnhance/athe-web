from collections import defaultdict
from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView

from atheweb.decorators import staff_required
from courses.models import Course, Semester, Student
from housepoints.models import Award

#: Shown when there is nothing on the books to award points against.
NO_SEMESTER = "There is no current semester to award points for."


def leaderboard(request: HttpRequest, slug: str | None = None) -> HttpResponse:
    """Show the house points leaderboard for a semester."""
    # Get semester (default to current active semester, then most recent)
    if slug:
        semester = get_object_or_404(Semester, slug=slug)
    else:
        # Not Semester.current(): between semesters the standings people just
        # finished earning are the ones worth showing, not an empty new slate.
        semester = Semester.latest_started()
        if semester is None:
            return render(
                request,
                "housepoints/leaderboard.html",
                {"semester": None, "leaderboard_data": []},
            )

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(user=request.user, semester=semester)
        except Student.DoesNotExist:
            student = None
    else:
        student = None

    totals_by_house = Award.objects.for_semester(semester).totals_by_house()
    leaderboard_data = sorted(
        (
            {
                "house": house.value,
                "house_display": house.label,
                "total_points": totals_by_house[house.value],
            }
            for house in Student.House
        ),
        key=lambda entry: -entry["total_points"],
    )

    # Get all semesters with any scores for navigation
    semesters = Semester.objects.filter(
        Exists(Award.objects.filter(semester=OuterRef("pk")))
    )

    return render(
        request,
        "housepoints/leaderboard.html",
        {
            "semester": semester,
            "student": student,
            "leaderboard_data": leaderboard_data,
            "semesters": semesters,
            "is_frozen": semester.house_points_freeze_date is not None,
            "freeze_date": semester.house_points_freeze_date,
        },
    )


class AwardResults:
    """Per-row outcomes of a bulk award run, and the summary messages for them."""

    def __init__(self) -> None:
        self.success: list[str] = []
        self.errors: list[str] = []

    def record(self, name: str, points: int, house: Student.House) -> None:
        self.success.append(f"{name}: +{points} pts ({house.label})")

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def report(self, request: HttpRequest) -> None:
        if self.success:
            messages.success(
                request, f"Successfully created {len(self.success)} awards."
            )
        if self.errors:
            messages.warning(request, f"{len(self.errors)} awards failed to create.")


class BulkAwardForm(forms.Form):
    """Form for bulk awarding points to multiple students."""

    award_type = forms.ChoiceField(
        choices=Award.AwardType.choices, help_text="Type of award to give"
    )
    airtable_names = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 10, "placeholder": "Enter one airtable name per line"}
        ),
        help_text="Enter airtable names, one per line",
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

    def clean_airtable_names(self) -> list[str]:
        """Parse airtable names from textarea."""
        airtable_names_text = self.cleaned_data["airtable_names"]
        airtable_names = [
            n.strip() for n in airtable_names_text.strip().split("\n") if n.strip()
        ]
        return airtable_names


class BulkAwardView(UserPassesTestMixin, View):
    """Staff-only view for bulk creating awards."""

    def test_func(self) -> bool:
        """Only staff can access this view."""
        return self.request.user.is_staff  # type: ignore[attr-defined]

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the bulk award form."""
        semester = Semester.current()
        if semester is None:
            messages.error(request, NO_SEMESTER)
            return redirect("index")

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
        semester = Semester.current()
        if semester is None:
            messages.error(request, NO_SEMESTER)
            return redirect("index")

        form = BulkAwardForm(request.POST)
        results = AwardResults()

        if form.is_valid():
            award_type = form.cleaned_data["award_type"]
            airtable_names = form.cleaned_data["airtable_names"]
            points = form.cleaned_data["points"]
            description = form.cleaned_data["description"]

            # Use default points if not specified
            if points is None:
                points = Award.DEFAULT_POINTS.get(award_type, 0)

            for airtable_name in airtable_names:
                try:
                    # Find the student record
                    students = Student.objects.select_related("user").filter(
                        airtable_name=airtable_name, semester=semester
                    )

                    # Check for duplicate airtable_names (should be impossible but validate)
                    if students.count() > 1:
                        results.fail(
                            f"{airtable_name}: Multiple students found with this airtable name"
                        )
                        continue

                    if students.count() == 0:
                        results.fail(
                            f"{airtable_name}: Not enrolled in {semester.name}"
                        )
                        continue

                    student = students.first()
                    assert student is not None

                    if not student.house:
                        results.fail(f"{airtable_name}: No house assigned")
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
                    results.record(airtable_name, points, Student.House(student.house))
                # One bad row must not abort the rest of the bulk award
                except Exception as e:  # noqa: BLE001
                    results.fail(f"{airtable_name}: {e!s}")

            results.report(request)

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
            .order_by("airtable_name")
        )

        students_list = []
        for student in students:
            if student.user is not None:
                first_name = student.user.first_name.lower()
                last_name = student.user.last_name.lower()
                username = student.user.username.lower()
                display_name = student.user.get_full_name()
            else:
                first_name = ""
                last_name = ""
                username = ""
                display_name = student.airtable_name

            students_list.append(
                {
                    "airtable_name": student.airtable_name,
                    "display": display_name,
                    # Add searchable fields
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username,
                }
            )

        return json.dumps(students_list)


class SingleAwardForm(forms.ModelForm):
    """Form for creating a single house-level award."""

    points = forms.IntegerField(
        required=False,
        help_text="Override default points (leave blank for default)",
    )

    class Meta:
        model = Award
        fields = ["house", "award_type", "points", "description"]
        help_texts = {
            "house": "Which house should receive this award?",
            "award_type": "Type of award to give",
            "description": "Optional description for this award",
        }

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        # Make house required for single awards
        self.fields["house"].required = True


class SingleAwardView(UserPassesTestMixin, CreateView):
    """Staff-only view for creating a single house-level award."""

    model = Award
    form_class = SingleAwardForm
    template_name = "housepoints/single_award.html"
    success_url = reverse_lazy("housepoints:single_award")

    def test_func(self) -> bool:
        """Only staff can access this view."""
        return self.request.user.is_staff  # type: ignore[attr-defined]

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add semester and default points to context."""
        context = super().get_context_data(**kwargs)
        context["semester"] = Semester.current()
        if context["semester"] is None:
            messages.error(self.request, NO_SEMESTER)
        else:
            context["default_points"] = Award.DEFAULT_POINTS
        return context

    def form_valid(self, form):  # type: ignore[no-untyped-def]
        """Set semester, awarded_by, and default points if needed."""
        semester = Semester.current()
        if semester is None:
            messages.error(self.request, NO_SEMESTER)
            return redirect("index")

        # Set the semester and awarded_by
        form.instance.semester = semester
        form.instance.awarded_by = self.request.user
        form.instance.student = None  # House-level award has no student

        # Use default points if not specified
        if form.cleaned_data["points"] is None:
            award_type = form.cleaned_data["award_type"]
            form.instance.points = Award.DEFAULT_POINTS.get(award_type, 0)

        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Successfully awarded {form.instance.points} points to "
            f"{form.instance.get_house_display()}!",  # type: ignore[attr-defined]
        )
        return response


@login_required
def my_awards(request: HttpRequest) -> HttpResponse:
    """Show all awards earned by the current user across semesters."""
    student_records = (
        Student.objects.filter(user=request.user)
        .select_related("semester")
        .annotate(total_points=Sum("awards__points"))
    )

    awards = (
        Award.objects.filter(student__in=student_records)
        .select_related("student__semester")
        .order_by("-awarded_at")
    )

    semester_totals = [
        {
            "semester": student.semester,
            "house": Student.House(student.house).label
            if student.house
            else "Unassigned",
            "total": student.total_points or 0,  # type: ignore[attr-defined]
        }
        for student in student_records
    ]

    return render(
        request,
        "housepoints/my_awards.html",
        {
            "awards": awards,
            "semester_totals": semester_totals,
        },
    )


class AttendanceBulkForm(forms.Form):
    """Form for bulk awarding attendance points to students in a class."""

    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        help_text="Select the class to award attendance for",
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Description for the attendance awards",
    )

    def __init__(self, *args, user=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        # Courses in a semester that has not ended. The default below picked
        # from exactly this set already, so anything narrower left the dropdown
        # empty while still preselecting a course.
        courses = Course.objects.filter(is_club=False).unfinished()
        self.fields["course"].queryset = courses.select_related(  # type: ignore[attr-defined]
            "semester"
        )

        # Set default to a course the user leads, if any
        if user is not None:
            led_courses = Course.objects.run_by(user).filter(is_club=False).unfinished()
            if led_courses.exists():
                self.fields["course"].initial = led_courses.first()


@login_required
def house_detail(request: HttpRequest, slug: str, house: str) -> HttpResponse:
    """Show detailed breakdown of points by category for a house (student view)."""
    semester = get_object_or_404(Semester, slug=slug)

    if house not in Student.House.values:
        messages.error(request, "Invalid house specified.")
        return redirect("housepoints:leaderboard_semester", slug=slug)

    # Check if user has access (staff or student in this specific house)
    assert isinstance(request.user, User)
    if not request.user.is_staff:
        student = Student.objects.filter(
            user=request.user, semester=semester, house=house
        ).first()
        if not student:
            messages.error(
                request, "You can only view detailed stats for your own house."
            )
            return redirect("housepoints:leaderboard_semester", slug=slug)

    awards_query = Award.objects.for_semester(semester).filter(house=house)

    # Aggregate points by category
    category_totals = (
        awards_query.values("award_type")
        .annotate(total_points=Sum("points"))
        .order_by("-total_points")
    )

    category_data = [
        {
            "award_type": entry["award_type"],
            "display_name": Award.AwardType(entry["award_type"]).label,
            "total_points": entry["total_points"] or 0,
        }
        for entry in category_totals
    ]

    # Calculate grand total
    grand_total = sum(c["total_points"] for c in category_data)

    house_display = Student.House(house).label

    return render(
        request,
        "housepoints/house_detail.html",
        {
            "semester": semester,
            "house": house,
            "house_display": house_display,
            "category_data": category_data,
            "grand_total": grand_total,
            "is_frozen": semester.house_points_freeze_date is not None,
            "freeze_date": semester.house_points_freeze_date,
        },
    )


@staff_required(
    message="This view is only available to staff members.",
    redirect_to="housepoints:leaderboard",
)
def house_detail_staff(request: HttpRequest, slug: str, house: str) -> HttpResponse:
    """Show detailed student x category breakdown for a house (staff view)."""
    semester = get_object_or_404(Semester, slug=slug)

    if house not in Student.House.values:
        messages.error(request, "Invalid house specified.")
        return redirect("housepoints:leaderboard_semester", slug=slug)

    awards_query = Award.objects.for_semester(semester, respect_freeze=False).filter(
        house=house
    )

    # Get all students in this house for the semester
    students = (
        Student.objects.filter(semester=semester, house=house)
        .select_related("user")
        .order_by("airtable_name")
    )

    # Award types actually used, in the order they are declared on the enum
    used = set(awards_query.values_list("award_type", flat=True))
    used_award_types = [at for at in Award.AwardType.values if at in used]

    # Build header row with short names for compact display
    headers = [Award.SHORT_NAMES.get(at, at) for at in used_award_types]

    # One grouped query gives every cell of the student x category grid
    points_by_row: dict[int | None, dict[str, int]] = defaultdict(dict)
    for entry in awards_query.values("student", "award_type").annotate(
        total=Sum("points")
    ):
        points_by_row[entry["student"]][entry["award_type"]] = entry["total"] or 0

    def build_row(
        key: int | None, name: str, student: Student | None
    ) -> dict[str, Any]:
        points = [points_by_row[key].get(at, 0) for at in used_award_types]
        return {
            "student": student,
            "name": name,
            "points": points,
            "total": sum(points),
        }

    student_rows = [build_row(s.pk, s.airtable_name, s) for s in students]
    if None in points_by_row:
        student_rows.append(build_row(None, "(House-level awards)", None))

    column_totals_list = [
        sum(row["points"][i] for row in student_rows)
        for i in range(len(used_award_types))
    ]
    grand_total = sum(column_totals_list)

    house_display = Student.House(house).label

    return render(
        request,
        "housepoints/house_detail_staff.html",
        {
            "semester": semester,
            "house": house,
            "house_display": house_display,
            "headers": headers,
            "award_types": used_award_types,
            "student_rows": student_rows,
            "column_totals": column_totals_list,
            "grand_total": grand_total,
            "is_frozen": semester.house_points_freeze_date is not None,
            "freeze_date": semester.house_points_freeze_date,
        },
    )


class AttendanceBulkView(UserPassesTestMixin, View):
    """Staff-only view for bulk creating attendance awards for a class."""

    def test_func(self) -> bool:
        """Only staff can access this view."""
        return self.request.user.is_staff  # type: ignore[attr-defined]

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the attendance bulk award form."""
        form = AttendanceBulkForm(user=request.user)  # type: ignore[arg-type]

        return render(
            request,
            "housepoints/attendance_bulk.html",
            {
                "form": form,
                "results": None,
                "students": [],
                "selected_course": None,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        """Process attendance bulk award creation."""
        form = AttendanceBulkForm(request.POST, user=request.user)  # type: ignore[arg-type]

        # Check if this is a "load students" action or the final submission
        if "load_students" in request.POST:
            return self._handle_load_students(request, form)

        return self._handle_award_submission(request, form)

    def _handle_load_students(
        self, request: HttpRequest, form: AttendanceBulkForm
    ) -> HttpResponse:
        """Handle loading students for a selected course."""
        if form.is_valid():
            course = form.cleaned_data["course"]
            students = list(
                course.students.select_related("user")
                .filter(house__isnull=False)
                .exclude(house="")
                .order_by("airtable_name")
            )

            # Pre-populate description with date and course name
            today_str = timezone.now().date().strftime("%Y-%m-%d")
            default_description = f"Attendance on {today_str} for {course.name}"

            # Create a new form with the description pre-filled
            form_data = request.POST.copy()
            if not form_data.get("description"):
                form_data["description"] = default_description
            updated_form = AttendanceBulkForm(form_data, user=request.user)  # type: ignore[arg-type]

            points = Award.class_attendance_points(course, students)
            students_with_counts = [
                {
                    "student": student,
                    "total_points": points[student.pk][0],
                    "points": points[student.pk][1],
                }
                for student in students
            ]

            return render(
                request,
                "housepoints/attendance_bulk.html",
                {
                    "form": updated_form,
                    "results": None,
                    "students": students_with_counts,
                    "selected_course": course,
                    "points_threshold": (
                        5 * course.semester.house_points_class_threshold
                    ),
                },
            )

        return render(
            request,
            "housepoints/attendance_bulk.html",
            {
                "form": form,
                "results": None,
                "students": [],
                "selected_course": None,
            },
        )

    def _handle_award_submission(
        self, request: HttpRequest, form: AttendanceBulkForm
    ) -> HttpResponse:
        """Handle the final award submission."""
        results = AwardResults()

        if form.is_valid():
            course = form.cleaned_data["course"]
            description = form.cleaned_data.get("description") or ""

            # Get selected student IDs from the checkboxes
            selected_student_ids = request.POST.getlist("students")

            if not selected_student_ids:
                results.fail("No students selected for attendance.")
            else:
                # Get the students who were checked
                students = Student.objects.filter(
                    pk__in=selected_student_ids, enrolled_courses=course
                ).select_related("user")
                attendance_points = Award.class_attendance_points(course, students)

                for student in students:
                    try:
                        if not student.house:
                            results.fail(f"{student.airtable_name}: No house assigned")
                            continue

                        _, points = attendance_points[student.pk]

                        # Create the attendance award
                        Award.objects.create(
                            semester=course.semester,
                            student=student,
                            house=student.house,
                            award_type=Award.AwardType.CLASS_ATTENDANCE,
                            points=points,
                            description=description,
                            awarded_by=request.user,
                        )
                        results.record(
                            student.airtable_name,
                            points,
                            Student.House(student.house),
                        )
                    # One bad row must not abort the rest of the bulk award
                    except Exception as e:  # noqa: BLE001
                        results.fail(f"{student.airtable_name}: {e!s}")

            results.report(request)

        # Re-render with results but without students list
        # (they should select class again for next batch)
        return render(
            request,
            "housepoints/attendance_bulk.html",
            {
                "form": AttendanceBulkForm(user=request.user),  # type: ignore[arg-type]
                "results": results,
                "students": [],
                "selected_course": None,
            },
        )

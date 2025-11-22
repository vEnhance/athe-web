from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Sum

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView

from courses.models import Course, Semester, Student
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

    try:
        student = Student.objects.get(user=request.user, semester=semester)
    except Student.DoesNotExist:
        student = None

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
                        results["errors"].append(
                            f"{airtable_name}: Multiple students found with this airtable name"
                        )
                        continue

                    if students.count() == 0:
                        results["errors"].append(
                            f"{airtable_name}: Not enrolled in {semester.name}"
                        )
                        continue

                    student = students.first()
                    assert student is not None

                    if not student.house:
                        results["errors"].append(f"{airtable_name}: No house assigned")
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
                        f"{airtable_name}: +{points} pts ({student.get_house_display()})"  # type: ignore[attr-defined]
                    )
                except Exception as e:
                    results["errors"].append(f"{airtable_name}: {str(e)}")

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

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add semester and default points to context."""
        context = super().get_context_data(**kwargs)
        try:
            context["semester"] = self._get_current_semester()
            context["default_points"] = Award.DEFAULT_POINTS
        except ValueError as e:
            messages.error(self.request, str(e))
            context["semester"] = None
        return context

    def form_valid(self, form):  # type: ignore[no-untyped-def]
        """Set semester, awarded_by, and default points if needed."""
        try:
            semester = self._get_current_semester()
        except ValueError as e:
            messages.error(self.request, str(e))
            return redirect("home:index")

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
        today = date.today()
        # Filter courses to those in semesters that haven't ended
        self.fields["course"].queryset = Course.objects.filter(  # type: ignore[attr-defined]
            semester__end_date__gte=today, is_club=False
        ).select_related("semester")

        # Set default to a course the user leads, if any
        if user is not None:
            led_courses = Course.objects.filter(
                leaders=user, semester__end_date__gte=today, is_club=False
            )
            if led_courses.exists():
                self.fields["course"].initial = led_courses.first()


@login_required
def house_detail(request: HttpRequest, slug: str, house: str) -> HttpResponse:
    """Show detailed breakdown of points by category for a house (student view)."""
    semester = get_object_or_404(Semester, slug=slug)

    # Validate house code
    valid_houses = [code for code, _ in Student.House.choices]
    if house not in valid_houses:
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

    # Get awards for this house, respecting freeze date
    awards_query = Award.objects.filter(semester=semester, house=house)
    if semester.house_points_freeze_date:
        awards_query = awards_query.filter(
            awarded_at__lte=semester.house_points_freeze_date
        )

    # Aggregate points by category
    category_totals = (
        awards_query.values("award_type")
        .annotate(total_points=Sum("points"))
        .order_by("-total_points")
    )

    # Build category data with display names
    category_data = []
    for entry in category_totals:
        award_type = entry["award_type"]
        display_name = dict(Award.AwardType.choices).get(award_type, award_type)
        category_data.append(
            {
                "award_type": award_type,
                "display_name": display_name,
                "total_points": entry["total_points"] or 0,
            }
        )

    # Calculate grand total
    grand_total = sum(c["total_points"] for c in category_data)

    # Get house display name
    house_display = dict(Student.House.choices).get(house, house)

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


@login_required
def house_detail_staff(request: HttpRequest, slug: str, house: str) -> HttpResponse:
    """Show detailed student x category breakdown for a house (staff view)."""
    # Staff only
    assert isinstance(request.user, User)
    if not request.user.is_staff:
        messages.error(request, "This view is only available to staff members.")
        return redirect("housepoints:leaderboard_semester", slug=slug)

    semester = get_object_or_404(Semester, slug=slug)

    # Validate house code
    valid_houses = [code for code, _ in Student.House.choices]
    if house not in valid_houses:
        messages.error(request, "Invalid house specified.")
        return redirect("housepoints:leaderboard_semester", slug=slug)

    # Get awards for this house, respecting freeze date
    awards_query = Award.objects.filter(semester=semester, house=house)
    if semester.house_points_freeze_date:
        awards_query = awards_query.filter(
            awarded_at__lte=semester.house_points_freeze_date
        )

    # Get all students in this house for the semester
    students = (
        Student.objects.filter(semester=semester, house=house)
        .select_related("user")
        .order_by("airtable_name")
    )

    # Get all award types that have been used
    used_award_types = list(set(awards_query.values_list("award_type", flat=True)))

    # Order award types by the choices order
    award_type_order = [code for code, _ in Award.AwardType.choices]
    used_award_types.sort(
        key=lambda x: award_type_order.index(x) if x in award_type_order else 999
    )

    # Build header row with short names for compact display
    headers = [Award.SHORT_NAMES.get(at, at) for at in used_award_types]

    # Build student rows
    student_rows = []
    column_totals = {at: 0 for at in used_award_types}

    for student in students:
        # Get points per category for this student
        student_awards = awards_query.filter(student=student)
        if semester.house_points_freeze_date:
            student_awards = student_awards.filter(
                awarded_at__lte=semester.house_points_freeze_date
            )

        category_points = dict(
            student_awards.values("award_type")
            .annotate(total=Sum("points"))
            .values_list("award_type", "total")
        )

        row_data = []
        row_total = 0
        for award_type in used_award_types:
            points = category_points.get(award_type, 0) or 0
            row_data.append(points)
            row_total += points
            column_totals[award_type] += points

        student_rows.append(
            {
                "student": student,
                "name": student.airtable_name,
                "points": row_data,
                "total": row_total,
            }
        )

    # Also include house-level awards (no student)
    house_awards = awards_query.filter(student__isnull=True)
    if house_awards.exists():
        house_category_points = dict(
            house_awards.values("award_type")
            .annotate(total=Sum("points"))
            .values_list("award_type", "total")
        )

        row_data = []
        row_total = 0
        for award_type in used_award_types:
            points = house_category_points.get(award_type, 0) or 0
            row_data.append(points)
            row_total += points
            column_totals[award_type] += points

        student_rows.append(
            {
                "student": None,
                "name": "(House-level awards)",
                "points": row_data,
                "total": row_total,
            }
        )

    # Build column totals row
    column_totals_list = [column_totals[at] for at in used_award_types]
    grand_total = sum(column_totals_list)

    # Get house display name
    house_display = dict(Student.House.choices).get(house, house)

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
            today_str = date.today().strftime("%Y-%m-%d")
            default_description = f"Attendance on {today_str} for {course.name}"

            # Create a new form with the description pre-filled
            form_data = request.POST.copy()
            if not form_data.get("description"):
                form_data["description"] = default_description
            updated_form = AttendanceBulkForm(form_data, user=request.user)  # type: ignore[arg-type]

            # Calculate attendance points for each student
            # Use total points instead of count to handle legacy imports
            threshold = course.semester.house_points_class_threshold
            points_threshold = 5 * threshold
            students_with_counts = []
            for student in students:
                total_points = (
                    Award.objects.filter(
                        semester=course.semester,
                        student=student,
                        award_type=Award.AwardType.CLASS_ATTENDANCE,
                    ).aggregate(total=Sum("points"))["total"]
                    or 0
                )
                points = 5 if total_points < points_threshold else 3
                students_with_counts.append(
                    {
                        "student": student,
                        "total_points": total_points,
                        "points": points,
                    }
                )

            return render(
                request,
                "housepoints/attendance_bulk.html",
                {
                    "form": updated_form,
                    "results": None,
                    "students": students_with_counts,
                    "selected_course": course,
                    "points_threshold": points_threshold,
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
        results = {"success": [], "errors": []}

        if form.is_valid():
            course = form.cleaned_data["course"]
            description = form.cleaned_data.get("description") or ""
            threshold = course.semester.house_points_class_threshold
            points_threshold = 5 * threshold

            # Get selected student IDs from the checkboxes
            selected_student_ids = request.POST.getlist("students")

            if not selected_student_ids:
                results["errors"].append("No students selected for attendance.")
            else:
                # Get the students who were checked
                students = Student.objects.filter(
                    pk__in=selected_student_ids, enrolled_courses=course
                ).select_related("user")

                for student in students:
                    try:
                        if not student.house:
                            results["errors"].append(
                                f"{student.airtable_name}: No house assigned"
                            )
                            continue

                        # Calculate points based on total attendance points
                        # Use total points instead of count to handle legacy imports
                        total_points = (
                            Award.objects.filter(
                                semester=course.semester,
                                student=student,
                                award_type=Award.AwardType.CLASS_ATTENDANCE,
                            ).aggregate(total=Sum("points"))["total"]
                            or 0
                        )
                        points = 5 if total_points < points_threshold else 3

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
                        results["success"].append(
                            f"{student.airtable_name}: +{points} pts "
                            f"({student.get_house_display()})"  # type: ignore[attr-defined]
                        )
                    except Exception as e:
                        results["errors"].append(f"{student.airtable_name}: {str(e)}")

            if results["success"]:
                messages.success(
                    request, f"Successfully created {len(results['success'])} awards."
                )
            if results["errors"]:
                messages.warning(
                    request, f"{len(results['errors'])} awards failed to create."
                )

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

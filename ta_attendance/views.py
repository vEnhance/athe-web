from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import AttendanceForm
from .models import Attendance


@login_required
def my_attendance(request: HttpRequest) -> HttpResponse:
    """View for staff to log and view their attendance records."""
    assert isinstance(request.user, User)
    if not request.user.is_staff:
        messages.error(request, "You must be a staff member to access this page.")
        return redirect("home:index")

    if request.method == "POST":
        form = AttendanceForm(request.POST)
        if form.is_valid():
            attendance = form.save(commit=False)
            attendance.user = request.user
            try:
                with transaction.atomic():
                    attendance.save()
                messages.success(
                    request,
                    f"Attendance recorded for {attendance.club.name} on {attendance.date}.",
                )
            except IntegrityError:
                messages.error(
                    request,
                    f"You already have an attendance record for {form.cleaned_data['club'].name} on {form.cleaned_data['date']}.",
                )
            return redirect("ta_attendance:my_attendance")
    else:
        form = AttendanceForm()

    # Get all attendance records for this user
    records = Attendance.objects.filter(user=request.user).select_related(
        "club", "club__semester"
    )

    return render(
        request,
        "ta_attendance/my_attendance.html",
        {
            "form": form,
            "records": records,
        },
    )


@login_required
def all_attendance(request: HttpRequest) -> HttpResponse:
    """View for superusers to see all attendance records."""
    assert isinstance(request.user, User)
    if not request.user.is_superuser:
        messages.error(request, "You must be a superuser to access this page.")
        return redirect("home:index")

    records = Attendance.objects.all().select_related("user", "club", "club__semester")

    return render(
        request,
        "ta_attendance/all_attendance.html",
        {
            "records": records,
        },
    )

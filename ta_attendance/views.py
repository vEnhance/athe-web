from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from atheweb.decorators import staff_required, superuser_required

from .forms import AttendanceForm
from .models import Attendance


@staff_required()
def my_attendance(request: HttpRequest) -> HttpResponse:
    """View for staff to log and view their attendance records."""
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


@superuser_required()
def all_attendance(request: HttpRequest) -> HttpResponse:
    """View for superusers to see all attendance records."""
    records = Attendance.objects.all().select_related("user", "club", "club__semester")

    return render(
        request,
        "ta_attendance/all_attendance.html",
        {
            "records": records,
        },
    )

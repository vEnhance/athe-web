from django.contrib import admin

from courses.models import Course, CourseMeeting, Semester, Student


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "start_date", "end_date", "house_points_freeze_date")
    prepopulated_fields = {"slug": ("name",)}


class CourseMeetingInline(admin.TabularInline):
    model = CourseMeeting
    extra = 3
    fields = ("start_time", "title", "reminder_sent")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "is_club", "semester", "instructor")
    list_filter = ("is_club", "semester", "difficulty")
    search_fields = ("name", "description")
    autocomplete_fields = ("instructor",)
    inlines = [CourseMeetingInline]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "semester", "house")
    list_filter = ("semester", "house")
    search_fields = ("user__username", "user__email")
    filter_horizontal = ("enrolled_courses",)

    def formfield_for_manytomany(self, db_field, request, **kwargs):  # type: ignore
        """Filter enrolled_courses to only show courses from the student's semester."""
        if db_field.name == "enrolled_courses":
            # Get the student instance being edited
            student_id = request.resolver_match.kwargs.get("object_id")  # type: ignore[attr-defined]
            if student_id:
                try:
                    student = Student.objects.get(pk=student_id)
                    # Filter courses to only those in the student's semester
                    kwargs["queryset"] = Course.objects.filter(
                        semester=student.semester
                    )
                except Student.DoesNotExist:
                    pass
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(CourseMeeting)
class CourseMeetingAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "start_time", "reminder_sent")
    list_filter = ("course", "reminder_sent", "start_time")
    search_fields = ("title", "course__name")
    date_hierarchy = "start_time"

from django.contrib import admin

from courses.models import Course, CourseMeeting, Semester, Student


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "start_date", "end_date")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "semester", "instructor", "difficulty")
    list_filter = ("semester", "difficulty")
    search_fields = ("name", "description")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "semester")
    list_filter = ("semester",)
    search_fields = ("user__username", "user__email")
    filter_horizontal = ("enrolled_courses",)


@admin.register(CourseMeeting)
class CourseMeetingAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "start_time", "reminder_sent")
    list_filter = ("course", "reminder_sent", "start_time")
    search_fields = ("title", "course__name")
    date_hierarchy = "start_time"

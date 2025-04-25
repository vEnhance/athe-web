from django.contrib import admin

from courses.models import Course, Semester

admin.site.register(Semester)
admin.site.register(Course)

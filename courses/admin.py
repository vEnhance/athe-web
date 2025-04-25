from django.contrib import admin

from .models import Course, Semester

admin.site.register(Semester)
admin.site.register(Course)

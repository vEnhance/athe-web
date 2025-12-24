"""
URL configuration for atheweb project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/favicon.ico", permanent=True),
    ),
    path(
        "cal/",
        RedirectView.as_view(pattern_name="courses:calendar", permanent=False),
    ),
    path("admin/", admin.site.urls),
    path("hijack/", include("hijack.urls")),
    path("catalog/", include("courses.urls")),
    path("house-points/", include("housepoints.urls")),
    path("ta-attendance/", include("ta_attendance.urls")),
    path("accounts/", include("allauth.urls")),
    path("reg/", include("reg.urls")),
    path("yearbook/", include("yearbook.urls")),
    path("blog/", include("weblog.urls")),
    path("misc/", include("misc.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="logout",
    ),
    path("", include("home.urls")),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

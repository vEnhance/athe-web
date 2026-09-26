from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import URLPattern, path, reverse

admin.site.unregister(User)


def reset_link(request: HttpRequest, user: User) -> str:
    """The same link allauth's reset flow would email, expiring the same way."""
    path = reverse(
        "account_reset_password_from_key",
        kwargs={
            "uidb36": user_pk_to_url_str(user),
            "key": default_token_generator.make_token(user),
        },
    )
    return request.build_absolute_uri(path)


@admin.register(User)
class AtheUserAdmin(UserAdmin):
    search_fields = (*UserAdmin.search_fields, "students__airtable_name")

    def get_urls(self) -> list[URLPattern]:
        return [
            path(
                "<int:user_id>/reset-link/",
                self.admin_site.admin_view(self.make_reset_link),
                name="auth_user_reset_link",
            ),
            *super().get_urls(),
        ]

    def make_reset_link(self, request: HttpRequest, user_id: int) -> HttpResponse:
        if not request.user.is_superuser:  # type: ignore[attr-defined]
            raise PermissionDenied
        user = get_object_or_404(User, pk=user_id)
        self.message_user(request, f"{user.username}: {reset_link(request, user)}")
        return redirect("admin:auth_user_change", user.pk)

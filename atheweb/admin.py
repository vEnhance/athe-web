from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse

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
    actions = ["make_password_reset_links"]

    def has_reset_password_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser  # type: ignore[attr-defined]

    @admin.action(
        description="Make password reset links", permissions=["reset_password"]
    )
    def make_password_reset_links(
        self, request: HttpRequest, queryset: QuerySet[User]
    ) -> None:
        for user in queryset:
            self.message_user(
                request, f"{user.username}: {reset_link(request, user)}", messages.INFO
            )

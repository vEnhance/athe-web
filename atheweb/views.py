"""Views belonging to the project rather than to any one app."""

from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from atheweb.decorators import superuser_required
from dashboard.views import dashboard

MAX_RESET_SEARCH_RESULTS = 25


def index(request: HttpRequest) -> HttpResponse:
    """The site root: the dashboard once logged in, the public splash page if not.

    It answers with a different app's page depending on who is asking, so it
    cannot sit inside either of them without pointing one app at the other.
    """
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, "home/index.html")


def _reset_link(request: HttpRequest, user: User) -> str:
    """The same link allauth's reset flow would email, expiring the same way."""
    path = reverse(
        "account_reset_password_from_key",
        kwargs={
            "uidb36": user_pk_to_url_str(user),
            "key": default_token_generator.make_token(user),
        },
    )
    return request.build_absolute_uri(path)


def _find_users(query: str) -> QuerySet[User]:
    matches = (
        Q(username__icontains=query)
        | Q(email__icontains=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(students__airtable_name__icontains=query)
    )
    return (
        User.objects.filter(matches)
        .distinct()
        .prefetch_related("students__semester")
        .order_by("username")
    )


@superuser_required()
def password_reset_link(request: HttpRequest) -> HttpResponse:
    """Look up a forgetful student's account and make them a reset link.

    The site sends no email, so the admin passes the link on by hand, e.g. in
    the Discord DM where the student asked for help.
    """
    context: dict[str, object] = {}
    if request.method == "POST":
        target = get_object_or_404(User, pk=request.POST.get("user"))
        context |= {"target": target, "link": _reset_link(request, target)}
    elif query := request.GET.get("q", "").strip():
        users = _find_users(query)
        context |= {
            "query": query,
            "users": users[:MAX_RESET_SEARCH_RESULTS],
            "truncated": users.count() > MAX_RESET_SEARCH_RESULTS,
        }
    return render(request, "atheweb/password_reset_link.html", context)

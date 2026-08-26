"""Shared permission decorators for function-based views.

Class-based views use UserPassesTestMixin; these give function-based views the
same gate without each one hand-rolling an is_staff check, an error message and
a redirect.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

type View = Callable[..., HttpResponse]
type Decorator = Callable[[View], View]


def _permission_required(
    predicate: Callable[[Any], bool], default_message: str
) -> Callable[..., Decorator]:
    """Build a decorator factory gating a view on a property of request.user."""

    def factory(message: str | None = None, redirect_to: str = "index") -> Decorator:
        def decorate(view: View) -> View:
            @wraps(view)
            @login_required
            def wrapper(
                request: HttpRequest, *args: Any, **kwargs: Any
            ) -> HttpResponse:
                if not predicate(request.user):
                    messages.error(request, message or default_message)
                    return redirect(redirect_to)
                return view(request, *args, **kwargs)

            return wrapper

        return decorate

    return factory


staff_required = _permission_required(
    lambda user: user.is_staff,
    "You must be a staff member to access this page.",
)

superuser_required = _permission_required(
    lambda user: user.is_superuser,
    "You must be a superuser to access this page.",
)

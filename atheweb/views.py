"""Views belonging to the project rather than to any one app.

The site root is the only one so far. It answers with a different app's page
depending on who is asking, so it cannot sit inside either of them without
pointing one app at the other; the project package is above both.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from dashboard.views import dashboard


def index(request: HttpRequest) -> HttpResponse:
    """The site root: the dashboard once logged in, the public splash page if not."""
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, "home/index.html")

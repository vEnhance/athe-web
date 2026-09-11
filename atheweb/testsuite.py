"""Test-client wrapper and assertions shared by every app's tests.

The point of this module is to keep tests off the rendered HTML. A test that
greps the response bytes for a sentence breaks the next time someone rewords
the sentence, and passes for the wrong reason whenever the string it looks for
happens to appear somewhere else on the page. Assert on what the view computed
(``response.context``), on what a POST wrote (the model), or -- when the
question really is "does this user see this element" -- on a ``data-testid``.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, cast

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import Client

#: Every test user gets this; ``conftest`` swaps in a fast hasher.
PASSWORD = "password"  # noqa: S105

_TESTID = re.compile(rb'data-testid="([^"]*)"')


def testids(response: HttpResponse) -> list[str]:
    """Every ``data-testid`` in the response, in document order."""
    return [match.decode() for match in _TESTID.findall(response.content)]


class _TestIdText(HTMLParser):
    """Collects the text inside the element carrying a given ``data-testid``."""

    def __init__(self, testid: str) -> None:
        super().__init__()
        self.testid = testid
        self.tag = ""
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.depth:
            if tag == self.tag:
                self.depth += 1
        elif dict(attrs).get("data-testid") == self.testid:
            self.tag = tag
            self.depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self.depth and tag == self.tag:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)


def text_of(response: HttpResponse, testid: str) -> str:
    """The visible text inside one ``data-testid``, whitespace collapsed.

    For the values a page prints -- a point total, a name, a date -- when they
    are not already sitting in the context. Scoping to one element is what
    keeps this honest: a bare substring search over the whole page matches the
    navbar as readily as the thing under test.
    """
    parser = _TestIdText(testid)
    parser.feed(response.content.decode())
    assert parser.tag, f"no element with data-testid={testid!r}"
    return " ".join("".join(parser.parts).split())


class AtheClient:
    """A Django test client that knows who is logged in and checks statuses."""

    def __init__(self) -> None:
        self.client = Client()
        self.user: User | None = None

    def login(self, user: User | str) -> User:
        """Log in as an existing user, replacing whoever was logged in before."""
        if isinstance(user, str):
            user = User.objects.get(username=user)
        assert self.client.login(username=user.username, password=PASSWORD)
        self.user = user
        return user

    def logout(self) -> None:
        self.client.logout()
        self.user = None

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return cast(HttpResponse, self.client.get(url, **kwargs))

    def post(self, url: str, data: Any = None, **kwargs: Any) -> HttpResponse:
        return cast(HttpResponse, self.client.post(url, data or {}, **kwargs))

    def get_ok(self, url: str, **kwargs: Any) -> HttpResponse:
        response = self.get(url, **kwargs)
        assert response.status_code == 200, f"GET {url} gave {response.status_code}"
        return response

    def post_ok(self, url: str, data: Any = None, **kwargs: Any) -> HttpResponse:
        """POST a form expected to render again, e.g. because it failed to validate."""
        response = self.post(url, data, **kwargs)
        assert response.status_code == 200, f"POST {url} gave {response.status_code}"
        return response

    def get_redirects(self, target: str, url: str, **kwargs: Any) -> HttpResponse:
        return self._redirects(target, self.get(url, **kwargs), "GET", url)

    def post_redirects(
        self, target: str, url: str, data: Any = None, **kwargs: Any
    ) -> HttpResponse:
        return self._redirects(target, self.post(url, data, **kwargs), "POST", url)

    def get_denied(self, url: str, **kwargs: Any) -> HttpResponse:
        """GET a page this user may not see, however the view says no.

        Both a 403 and a bounce to the login page count: which one a view picks
        is a detail of whether it guards with a permission check or a login
        decorator, and tests about who can reach what should not have to care.
        """
        response = self.get(url, **kwargs)
        assert response.status_code in (302, 403, 404), (
            f"GET {url} gave {response.status_code}, expected to be refused"
        )
        return response

    def _redirects(
        self, target: str, response: HttpResponse, verb: str, url: str
    ) -> HttpResponse:
        assert response.status_code in (301, 302), (
            f"{verb} {url} gave {response.status_code}, expected a redirect"
        )
        location = response["Location"]
        assert location == target or location.startswith(f"{target}?"), (
            f"{verb} {url} redirected to {location}, expected {target}"
        )
        return response

    def testids(self, response: HttpResponse, prefix: str = "") -> list[str]:
        """The ``data-testid`` values on the page, for asserting on a whole group.

        Pass a prefix to ask what a section contains rather than whether one
        element is there: comparing ``testids(resp, "nav-")`` against a list
        catches an entry that has quietly been added as well as one that has
        gone missing.
        """
        return [t for t in testids(response) if t.startswith(prefix)]

    def text_of(self, response: HttpResponse, testid: str) -> str:
        return text_of(response, testid)

    def assert_testid(self, response: HttpResponse, *wanted: str) -> None:
        present = testids(response)
        for testid in wanted:
            assert testid in present, f"{testid} missing; page has {sorted(present)}"

    def assert_no_testid(self, response: HttpResponse, *unwanted: str) -> None:
        present = testids(response)
        for testid in unwanted:
            assert testid not in present, f"{testid} should not be on the page"

    def assert_testid_count(
        self, response: HttpResponse, testid: str, count: int
    ) -> None:
        found = testids(response).count(testid)
        assert found == count, f"{testid} appears {found} times, expected {count}"

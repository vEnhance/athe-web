import pytest
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    StreamingHttpResponse,
)

from atheweb.middleware import DropNoBodyContentMiddleware


def run(method: str, response: HttpResponseBase) -> HttpResponseBase:
    request = HttpRequest()
    request.method = method
    return DropNoBodyContentMiddleware(lambda _request: response)(request)


def test_head_response_keeps_headers_but_drops_body():
    response = HttpResponse(b"hello")
    response.headers["Content-Length"] = str(len(response.content))
    result = run("HEAD", response)
    assert result.content == b""
    assert result.headers["Content-Length"] == "5"


def test_get_response_keeps_body():
    assert run("GET", HttpResponse(b"hello")).content == b"hello"


@pytest.mark.parametrize("status", [204, 304])
def test_bodyless_status_drops_body_even_on_get(status: int):
    assert run("GET", HttpResponse(b"oops", status=status)).content == b""


def test_streaming_head_response_drops_body():
    result = run("HEAD", StreamingHttpResponse(iter([b"a", b"b"])))
    assert list(result.streaming_content) == []

"""Project-wide middleware.

Django leaves it to the WSGI server to discard bodies on responses that may not
have one; gunicorn does discard them, but logs a warning for each. Dropping the
body here keeps the production logs readable.
"""

from collections.abc import Callable

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    StreamingHttpResponse,
)

type GetResponse = Callable[[HttpRequest], HttpResponseBase]


def _forbids_body(request: HttpRequest, response: HttpResponseBase) -> bool:
    return (
        request.method == "HEAD"
        or 100 <= response.status_code < 200
        or response.status_code in (204, 304)
    )


class DropNoBodyContentMiddleware:
    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = self.get_response(request)
        if _forbids_body(request, response):
            if isinstance(response, StreamingHttpResponse):
                response.streaming_content = []
            elif isinstance(response, HttpResponse):
                response.content = b""
        return response

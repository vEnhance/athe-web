import datetime

from django import template
from django.template.defaultfilters import date as date_filter
from django.utils.html import format_html

register = template.Library()


@register.filter
def local_datetime(
    value: datetime.datetime | datetime.date | str | None,
    fmt: str = "N j, Y, g:i A",
) -> object:
    """Render a datetime as an interactive span showing local time on hover/click.

    Usage: {{ obj.datetime_field|local_datetime:"F j, Y g:i A e" }}

    The span shows server time by default. Hovering shows a tooltip with the
    user's local time, and clicking toggles between server and local time.
    Plain date objects (without time) are returned formatted without interaction.
    """
    if not value:
        return ""
    if not isinstance(value, datetime.datetime):
        return date_filter(value, fmt)

    try:
        iso = value.isoformat()
    except Exception:
        return date_filter(value, fmt)

    display = date_filter(value, fmt)
    return format_html(
        '<span class="local-datetime" data-utc="{}" tabindex="0">{}</span>',
        iso,
        display,
    )

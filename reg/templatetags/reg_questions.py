from typing import Any

from django import template
from django.forms import BoundField

register = template.Library()


@register.inclusion_tag("reg/components/question.html")
def question(field: BoundField) -> dict[str, Any]:
    """Render one questionnaire field as a heading, its note, then the widget.

    Usage: {% question form.email %}

    django-bootstrap5 puts help text underneath the widget, which reads badly
    when the widget is a 64-cell grid: by the time the clarification arrives
    the student has already answered. So the label becomes a heading and the
    help text sits directly under it, with bootstrap_field left to render the
    input (and any errors) alone.
    """
    return {"field": field}

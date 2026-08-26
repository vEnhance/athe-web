"""The order of the student registration pages, and where a student is in them.

The questionnaire is long enough that one page would be a scroll of doom, so it
is split into these steps. Each one saves to the database on its own, so
progress lives on the StudentRegistration row rather than in the session.
"""

from typing import Any

from django.urls import reverse

from .forms import (
    AvailabilityStepForm,
    ClassPreferenceStepForm,
    IdentityStepForm,
    RegistrationStepForm,
    SortingStepForm,
)
from .models import StudentRegistration

#: The pages of the questionnaire, in the order they are asked.
STEPS: tuple[type[RegistrationStepForm], ...] = (
    IdentityStepForm,
    ClassPreferenceStepForm,
    AvailabilityStepForm,
    SortingStepForm,
)

FIRST_STEP = STEPS[0]


def step_for(slug: str) -> type[RegistrationStepForm] | None:
    """The page served at this slug, or None if there is no such page."""
    return next((step for step in STEPS if step.slug == slug), None)


def completed(registration: StudentRegistration | None) -> set[str]:
    """Slugs of the pages this student has saved."""
    return set(registration.completed_steps) if registration else set()


def is_complete(registration: StudentRegistration | None) -> bool:
    """Whether every page has been saved."""
    return completed(registration).issuperset(step.slug for step in STEPS)


def next_incomplete(
    registration: StudentRegistration | None,
) -> type[RegistrationStepForm] | None:
    """The first page still to be filled in, or None when they are all done."""
    done = completed(registration)
    return next((step for step in STEPS if step.slug not in done), None)


def is_reachable(
    step: type[RegistrationStepForm], registration: StudentRegistration | None
) -> bool:
    """Whether a student may open this page yet.

    Pages open up one at a time so that the later ones always have a
    registration row to write to; once saved, a page stays open for edits.
    """
    done = completed(registration)
    return step.slug in done or all(
        earlier.slug in done for earlier in STEPS[: STEPS.index(step)]
    )


def progress(
    invite_id: Any,
    current: type[RegistrationStepForm],
    registration: StudentRegistration | None,
) -> list[dict[str, Any]]:
    """The progress bar: one entry per page, with links to the open ones."""
    done = completed(registration)
    return [
        {
            "title": step.title,
            "number": number,
            "done": step.slug in done,
            "current": step is current,
            "url": (
                reverse("reg:student-step", args=[invite_id, step.slug])
                if is_reachable(step, registration)
                else None
            ),
        }
        for number, step in enumerate(STEPS, 1)
    ]

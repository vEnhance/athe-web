import pytest
from django.urls import reverse

from atheweb.testsuite import AtheClient
from reg.models import StudentRegistration


@pytest.mark.django_db
def test_lists_every_question_and_choice(athe: AtheClient) -> None:
    resp = athe.get_ok(reverse("reg:quiz-questions"))
    athe.assert_testid_count(resp, "quiz-question", 5)
    assert athe.texts_of(resp, "quiz-choice")[:5] == [
        label for _, label in StudentRegistration.Challenge.choices
    ]

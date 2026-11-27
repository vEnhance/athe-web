from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import CLASS_ONLY_FIELDS, Course, Semester


@pytest.fixture
def superuser(athe: AtheClient, make_user: Callable[..., User]) -> User:
    user = make_user(username="admin", is_staff=True, is_superuser=True)
    athe.login(user)
    return user


@pytest.fixture
def one_of_each(
    make_semester: Callable[..., Semester], make_course: Callable[..., Course]
) -> dict[Course.Kind, Course]:
    semester = make_semester()
    return {
        kind: make_course(semester, name=kind.label, kind=kind) for kind in Course.Kind
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("model_name", "kind"),
    [
        ("classproxy", Course.Kind.CLASS),
        ("clubproxy", Course.Kind.CLUB),
        ("officehoursproxy", Course.Kind.OFFICE_HOURS),
    ],
)
def test_each_kind_has_its_own_admin_list(
    athe: AtheClient,
    superuser: User,
    one_of_each: dict[Course.Kind, Course],
    model_name: str,
    kind: Course.Kind,
):
    response = athe.get_ok(f"/admin/courses/{model_name}/")

    assert [c.pk for c in response.context["cl"].result_list] == [one_of_each[kind].pk]


@pytest.mark.django_db
def test_class_admin_form_has_class_fields_only(
    athe: AtheClient, superuser: User, one_of_each: dict[Course.Kind, Course]
):
    course = one_of_each[Course.Kind.CLASS]
    fields = athe.get_ok(course.get_admin_url()).context["adminform"].form.fields

    assert set(CLASS_ONLY_FIELDS) <= set(fields)
    assert "student_organizers" not in fields
    assert "kind" not in fields


@pytest.mark.django_db
def test_club_admin_form_has_club_fields_only(
    athe: AtheClient, superuser: User, one_of_each: dict[Course.Kind, Course]
):
    course = one_of_each[Course.Kind.CLUB]
    fields = athe.get_ok(course.get_admin_url()).context["adminform"].form.fields

    assert not set(CLASS_ONLY_FIELDS) & set(fields)
    assert "student_organizers" in fields


@pytest.mark.django_db
def test_admin_url_matches_kind(one_of_each: dict[Course.Kind, Course]):
    assert one_of_each[Course.Kind.CLASS].get_admin_url() == reverse(
        "admin:courses_classproxy_change", args=[one_of_each[Course.Kind.CLASS].pk]
    )
    assert one_of_each[Course.Kind.OFFICE_HOURS].get_admin_url() == reverse(
        "admin:courses_officehoursproxy_change",
        args=[one_of_each[Course.Kind.OFFICE_HOURS].pk],
    )


@pytest.mark.django_db
def test_club_admin_rejects_another_kind(
    athe: AtheClient, superuser: User, one_of_each: dict[Course.Kind, Course]
):
    class_pk = one_of_each[Course.Kind.CLASS].pk
    athe.get_redirects(
        reverse("admin:index"),
        reverse("admin:courses_clubproxy_change", args=[class_pk]),
    )


@pytest.mark.django_db
def test_adding_through_club_admin_makes_a_club(
    athe: AtheClient, superuser: User, make_semester: Callable[..., Semester]
):
    semester = make_semester()
    athe.post_redirects(
        reverse("admin:courses_clubproxy_changelist"),
        reverse("admin:courses_clubproxy_add"),
        {
            "name": "Chess Club",
            "semester": semester.pk,
            "description": "Chess",
            "meetings-TOTAL_FORMS": 0,
            "meetings-INITIAL_FORMS": 0,
        },
    )

    assert Course.objects.get(name="Chess Club").kind == Course.Kind.CLUB


@pytest.mark.django_db
@pytest.mark.parametrize(
    "class_only", [{"lesson_plan": "Week 1"}, {"discord_reminders_enabled": True}]
)
def test_clubs_cannot_hold_class_only_fields(
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    class_only: dict[str, object],
):
    with pytest.raises(IntegrityError):
        make_course(make_semester(), kind=Course.Kind.CLUB, **class_only)


@pytest.mark.django_db
def test_club_edit_form_omits_class_only_fields(
    athe: AtheClient, superuser: User, one_of_each: dict[Course.Kind, Course]
):
    club = one_of_each[Course.Kind.CLUB]
    response = athe.get_ok(reverse("courses:course_update", kwargs={"pk": club.pk}))

    assert not set(CLASS_ONLY_FIELDS) & set(response.context["form"].fields)


@pytest.mark.django_db
def test_class_edit_form_keeps_class_only_fields(
    athe: AtheClient, superuser: User, one_of_each: dict[Course.Kind, Course]
):
    course = one_of_each[Course.Kind.CLASS]
    response = athe.get_ok(reverse("courses:course_update", kwargs={"pk": course.pk}))

    assert set(CLASS_ONLY_FIELDS) <= set(response.context["form"].fields)

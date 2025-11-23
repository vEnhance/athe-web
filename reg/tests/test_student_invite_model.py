from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester

from reg.models import StudentInviteLink


@pytest.fixture
def student_invite_model_setup():
    """Set up test data for student invite model tests."""
    future_date = timezone.now() + timedelta(days=7)
    past_date = timezone.now() - timedelta(days=7)

    # Create semesters
    active_semester = Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=90),
    )
    ended_semester = Semester.objects.create(
        name="Spring 2024",
        slug="spring-2024",
        start_date=timezone.now().date() - timedelta(days=180),
        end_date=timezone.now().date() - timedelta(days=90),
    )

    return {
        "future_date": future_date,
        "past_date": past_date,
        "active_semester": active_semester,
        "ended_semester": ended_semester,
    }


@pytest.mark.django_db
def test_create_student_invite_link(student_invite_model_setup):
    """Test creating a student invite link."""
    invite = StudentInviteLink.objects.create(
        name="Test Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.id is not None
    assert invite.name == "Test Invite"
    assert invite.semester == student_invite_model_setup["active_semester"]
    assert invite.is_expired() is False
    assert invite.is_semester_ended() is False


@pytest.mark.django_db
def test_student_invite_is_expired_future_date(student_invite_model_setup):
    """Test that future dates are not expired."""
    invite = StudentInviteLink.objects.create(
        name="Future Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.is_expired() is False


@pytest.mark.django_db
def test_student_invite_is_expired_past_date(student_invite_model_setup):
    """Test that past dates are expired."""
    invite = StudentInviteLink.objects.create(
        name="Past Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["past_date"],
    )
    assert invite.is_expired() is True


@pytest.mark.django_db
def test_is_semester_ended_active_semester(student_invite_model_setup):
    """Test that active semester is not ended."""
    invite = StudentInviteLink.objects.create(
        name="Active Semester Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.is_semester_ended() is False


@pytest.mark.django_db
def test_is_semester_ended_past_semester(student_invite_model_setup):
    """Test that past semester is ended."""
    invite = StudentInviteLink.objects.create(
        name="Ended Semester Invite",
        semester=student_invite_model_setup["ended_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.is_semester_ended() is True


@pytest.mark.django_db
def test_student_invite_get_absolute_url(student_invite_model_setup):
    """Test the get_absolute_url method."""
    invite = StudentInviteLink.objects.create(
        name="Test Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    url = invite.get_absolute_url()
    assert url == reverse("reg:add-student", kwargs={"invite_id": invite.id})

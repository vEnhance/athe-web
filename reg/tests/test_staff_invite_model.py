from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from reg.models import StaffInviteLink


@pytest.mark.django_db
def test_create_invite_link():
    """Test creating a staff invite link."""
    future_date = timezone.now() + timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Test Invite",
        expiration_date=future_date,
    )
    assert invite.id is not None
    assert invite.name == "Test Invite"
    assert invite.is_expired() is False


@pytest.mark.django_db
def test_is_expired_future_date():
    """Test that future dates are not expired."""
    future_date = timezone.now() + timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Future Invite",
        expiration_date=future_date,
    )
    assert invite.is_expired() is False


@pytest.mark.django_db
def test_is_expired_past_date():
    """Test that past dates are expired."""
    past_date = timezone.now() - timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Past Invite",
        expiration_date=past_date,
    )
    assert invite.is_expired() is True


@pytest.mark.django_db
def test_get_absolute_url():
    """Test the get_absolute_url method."""
    future_date = timezone.now() + timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Test Invite",
        expiration_date=future_date,
    )
    url = invite.get_absolute_url()
    assert url == reverse("reg:add-staff", kwargs={"invite_id": invite.id})

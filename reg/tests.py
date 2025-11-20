from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester
from home.models import StaffPhotoListing

from .models import StaffInviteLink


class StaffInviteLinkModelTest(TestCase):
    """Tests for the StaffInviteLink model."""

    def setUp(self):
        """Set up test data."""
        self.future_date = timezone.now() + timedelta(days=7)
        self.past_date = timezone.now() - timedelta(days=7)

    def test_create_invite_link(self):
        """Test creating a staff invite link."""
        invite = StaffInviteLink.objects.create(
            name="Test Invite",
            expiration_date=self.future_date,
        )
        self.assertIsNotNone(invite.id)
        self.assertEqual(invite.name, "Test Invite")
        self.assertFalse(invite.is_expired())

    def test_is_expired_future_date(self):
        """Test that future dates are not expired."""
        invite = StaffInviteLink.objects.create(
            name="Future Invite",
            expiration_date=self.future_date,
        )
        self.assertFalse(invite.is_expired())

    def test_is_expired_past_date(self):
        """Test that past dates are expired."""
        invite = StaffInviteLink.objects.create(
            name="Past Invite",
            expiration_date=self.past_date,
        )
        self.assertTrue(invite.is_expired())

    def test_get_absolute_url(self):
        """Test the get_absolute_url method."""
        invite = StaffInviteLink.objects.create(
            name="Test Invite",
            expiration_date=self.future_date,
        )
        url = invite.get_absolute_url()
        self.assertEqual(url, reverse("reg:invite", kwargs={"invite_id": invite.id}))


class StaffInviteViewTest(TestCase):
    """Tests for the StaffInviteView."""

    def setUp(self):
        """Set up test data."""
        # Create staff photo listings
        self.staff1 = StaffPhotoListing.objects.create(
            display_name="John Doe",
            slug="john-doe",
            role="Instructor",
            category="instructor",
            biography="Test bio",
            ordering=0,
        )
        self.staff2 = StaffPhotoListing.objects.create(
            display_name="Jane Smith",
            slug="jane-smith",
            role="TA",
            category="ta",
            biography="Test bio",
            ordering=0,
        )

        # Create a user and link to staff2
        self.existing_user = User.objects.create_user(
            username="janesmith",
            password="testpass123",
            email="jane@example.com",
            first_name="Jane",
            last_name="Smith",
            is_staff=True,
        )
        self.staff2.user = self.existing_user
        self.staff2.save()

        # Create invite links
        self.valid_invite = StaffInviteLink.objects.create(
            name="Valid Invite",
            expiration_date=timezone.now() + timedelta(days=7),
        )
        self.expired_invite = StaffInviteLink.objects.create(
            name="Expired Invite",
            expiration_date=timezone.now() - timedelta(days=7),
        )

        # Create a semester and course
        self.semester = Semester.objects.create(
            name="Fall 2025",
            slug="fall-2025",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
        )
        self.course = Course.objects.create(
            name="Test Course",
            description="Test course description",
            semester=self.semester,
            instructor=self.staff1,
        )

    def test_get_staff_selection(self):
        """Test GET request shows staff selection form."""
        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/select_staff.html")
        self.assertContains(response, "John Doe")
        self.assertContains(response, "Jane Smith")

    def test_get_expired_invite(self):
        """Test GET request to expired invite shows error."""
        url = reverse("reg:invite", kwargs={"invite_id": self.expired_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/invite_expired.html")

    def test_post_staff_selection(self):
        """Test POST request to select staff listing."""
        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"staff_listing": self.staff1.id})
        self.assertEqual(response.status_code, 302)  # Redirect
        # Check session has staff_listing_id
        session = self.client.session
        self.assertEqual(session["staff_listing_id"], self.staff1.id)

    def test_post_staff_selection_already_registered(self):
        """Test POST request to select already registered staff shows error."""
        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"staff_listing": self.staff2.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/already_registered.html")
        self.assertContains(response, "janesmith")

    def test_get_registration_form(self):
        """Test GET request shows registration form when staff is selected."""
        # Set session
        session = self.client.session
        session["staff_listing_id"] = self.staff1.id
        session.save()

        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/register.html")
        self.assertContains(response, "John Doe")

    def test_post_registration_creates_user(self):
        """Test POST request creates user and links to staff listing."""
        # Set session
        session = self.client.session
        session["staff_listing_id"] = self.staff1.id
        session.save()

        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(
            url,
            {
                "username": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "password1": "testpass123!@#",
                "password2": "testpass123!@#",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirect to home

        # Check user was created
        user = User.objects.get(username="johndoe")
        self.assertTrue(user.is_staff)
        self.assertEqual(user.email, "john@example.com")
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")

        # Check staff listing is linked
        self.staff1.refresh_from_db()
        self.assertEqual(self.staff1.user, user)

        # Check user is logged in
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, "johndoe")

        # Check session is cleared
        session = self.client.session
        self.assertNotIn("staff_listing_id", session)

    def test_post_registration_adds_user_to_course_leaders(self):
        """Test that registration adds user to course leaders when they are instructor."""
        # Set session
        session = self.client.session
        session["staff_listing_id"] = self.staff1.id
        session.save()

        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(
            url,
            {
                "username": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "password1": "testpass123!@#",
                "password2": "testpass123!@#",
            },
        )
        self.assertEqual(response.status_code, 302)

        # Check user was added to course leaders
        user = User.objects.get(username="johndoe")
        self.course.refresh_from_db()
        self.assertIn(user, self.course.leaders.all())

    def test_post_registration_invalid_form(self):
        """Test POST request with invalid form shows errors."""
        # Set session
        session = self.client.session
        session["staff_listing_id"] = self.staff1.id
        session.save()

        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(
            url,
            {
                "username": "johndoe",
                "email": "invalid-email",  # Invalid email
                "first_name": "John",
                "last_name": "Doe",
                "password1": "testpass123!@#",
                "password2": "differentpass",  # Passwords don't match
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/register.html")
        # User should not be created
        self.assertFalse(User.objects.filter(username="johndoe").exists())

    def test_session_cleared_when_accessing_already_registered_staff(self):
        """Test that session is cleared when trying to register already registered staff."""
        # Set session to staff2 who already has a user
        session = self.client.session
        session["staff_listing_id"] = self.staff2.id
        session.save()

        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/already_registered.html")

        # Check session is cleared
        session = self.client.session
        self.assertNotIn("staff_listing_id", session)

    def test_multiple_courses_with_same_instructor(self):
        """Test that user is added to all courses where they are instructor."""
        # Create another course with the same instructor
        course2 = Course.objects.create(
            name="Test Course 2",
            description="Test course 2 description",
            semester=self.semester,
            instructor=self.staff1,
        )

        # Set session
        session = self.client.session
        session["staff_listing_id"] = self.staff1.id
        session.save()

        url = reverse("reg:invite", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(
            url,
            {
                "username": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "password1": "testpass123!@#",
                "password2": "testpass123!@#",
            },
        )
        self.assertEqual(response.status_code, 302)

        # Check user was added to both courses
        user = User.objects.get(username="johndoe")
        self.course.refresh_from_db()
        course2.refresh_from_db()
        self.assertIn(user, self.course.leaders.all())
        self.assertIn(user, course2.leaders.all())


class StaffInviteLinkAdminTest(TestCase):
    """Tests for the StaffInviteLink admin."""

    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@example.com",
        )
        self.client.login(username="admin", password="admin123")

    def test_admin_list_display(self):
        """Test that admin list page works."""
        url = reverse("admin:reg_staffinvitelink_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_create_invite(self):
        """Test creating invite link through admin."""
        url = reverse("admin:reg_staffinvitelink_add")
        response = self.client.post(
            url,
            {
                "name": "New Invite",
                "expiration_date_0": "2025-12-31",  # Date part
                "expiration_date_1": "23:59:59",  # Time part
            },
        )
        # Should redirect to changelist on success
        self.assertEqual(response.status_code, 302)

        # Check invite was created
        invite = StaffInviteLink.objects.get(name="New Invite")
        self.assertIsNotNone(invite)

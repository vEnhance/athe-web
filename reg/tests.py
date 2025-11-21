from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student
from home.models import StaffPhotoListing

from .models import StaffInviteLink, StudentInviteLink


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
        self.assertEqual(url, reverse("reg:add-staff", kwargs={"invite_id": invite.id}))


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
        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/select_staff.html")
        self.assertContains(response, "John Doe")
        self.assertContains(response, "Jane Smith")

    def test_get_expired_invite(self):
        """Test GET request to expired invite shows error."""
        url = reverse("reg:add-staff", kwargs={"invite_id": self.expired_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/invite_expired.html")

    def test_post_staff_selection(self):
        """Test POST request to select staff listing."""
        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"staff_listing": self.staff1.id})
        self.assertEqual(response.status_code, 302)  # Redirect
        # Check session has staff_listing_id
        session = self.client.session
        self.assertEqual(session["staff_listing_id"], self.staff1.id)

    def test_post_staff_selection_already_registered(self):
        """Test POST request to select already registered staff shows error."""
        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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

        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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

        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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

        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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

        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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

        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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

        url = reverse("reg:add-staff", kwargs={"invite_id": self.valid_invite.id})
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


class StudentInviteLinkModelTest(TestCase):
    """Tests for the StudentInviteLink model."""

    def setUp(self):
        """Set up test data."""
        self.future_date = timezone.now() + timedelta(days=7)
        self.past_date = timezone.now() - timedelta(days=7)

        # Create semesters
        self.active_semester = Semester.objects.create(
            name="Fall 2025",
            slug="fall-2025",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
        )
        self.ended_semester = Semester.objects.create(
            name="Spring 2024",
            slug="spring-2024",
            start_date=timezone.now().date() - timedelta(days=180),
            end_date=timezone.now().date() - timedelta(days=90),
        )

    def test_create_invite_link(self):
        """Test creating a student invite link."""
        invite = StudentInviteLink.objects.create(
            name="Test Invite",
            semester=self.active_semester,
            expiration_date=self.future_date,
        )
        self.assertIsNotNone(invite.id)
        self.assertEqual(invite.name, "Test Invite")
        self.assertEqual(invite.semester, self.active_semester)
        self.assertFalse(invite.is_expired())
        self.assertFalse(invite.is_semester_ended())

    def test_is_expired_future_date(self):
        """Test that future dates are not expired."""
        invite = StudentInviteLink.objects.create(
            name="Future Invite",
            semester=self.active_semester,
            expiration_date=self.future_date,
        )
        self.assertFalse(invite.is_expired())

    def test_is_expired_past_date(self):
        """Test that past dates are expired."""
        invite = StudentInviteLink.objects.create(
            name="Past Invite",
            semester=self.active_semester,
            expiration_date=self.past_date,
        )
        self.assertTrue(invite.is_expired())

    def test_is_semester_ended_active_semester(self):
        """Test that active semester is not ended."""
        invite = StudentInviteLink.objects.create(
            name="Active Semester Invite",
            semester=self.active_semester,
            expiration_date=self.future_date,
        )
        self.assertFalse(invite.is_semester_ended())

    def test_is_semester_ended_past_semester(self):
        """Test that past semester is ended."""
        invite = StudentInviteLink.objects.create(
            name="Ended Semester Invite",
            semester=self.ended_semester,
            expiration_date=self.future_date,
        )
        self.assertTrue(invite.is_semester_ended())

    def test_get_absolute_url(self):
        """Test the get_absolute_url method."""
        invite = StudentInviteLink.objects.create(
            name="Test Invite",
            semester=self.active_semester,
            expiration_date=self.future_date,
        )
        url = invite.get_absolute_url()
        self.assertEqual(
            url, reverse("reg:add-student", kwargs={"invite_id": invite.id})
        )


class StudentInviteViewTest(TestCase):
    """Tests for the StudentInviteView."""

    def setUp(self):
        """Set up test data."""
        # Create semester
        self.semester = Semester.objects.create(
            name="Fall 2025",
            slug="fall-2025",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
        )
        self.ended_semester = Semester.objects.create(
            name="Spring 2024",
            slug="spring-2024",
            start_date=timezone.now().date() - timedelta(days=180),
            end_date=timezone.now().date() - timedelta(days=90),
        )

        # Create students
        self.student1 = Student.objects.create(
            airtable_name="Alice Johnson",
            semester=self.semester,
            house=Student.House.BLOB,
        )
        self.student2 = Student.objects.create(
            airtable_name="Bob Smith",
            semester=self.semester,
            house=Student.House.CAT,
        )

        # Create a user and link to student2
        self.existing_user = User.objects.create_user(
            username="bobsmith",
            password="testpass123",
        )
        self.student2.user = self.existing_user
        self.student2.save()

        # Create invite links
        self.valid_invite = StudentInviteLink.objects.create(
            name="Valid Invite",
            semester=self.semester,
            expiration_date=timezone.now() + timedelta(days=7),
        )
        self.expired_invite = StudentInviteLink.objects.create(
            name="Expired Invite",
            semester=self.semester,
            expiration_date=timezone.now() - timedelta(days=7),
        )
        self.ended_semester_invite = StudentInviteLink.objects.create(
            name="Ended Semester Invite",
            semester=self.ended_semester,
            expiration_date=timezone.now() + timedelta(days=7),
        )

    def test_get_login_choice(self):
        """Test GET request shows login choice form when not logged in."""
        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/login_choice.html")
        self.assertContains(response, "Do you already have an account?")

    def test_get_expired_invite(self):
        """Test GET request to expired invite shows error."""
        url = reverse("reg:add-student", kwargs={"invite_id": self.expired_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/student_invite_expired.html")
        self.assertContains(response, "expired")

    def test_get_ended_semester_invite(self):
        """Test GET request to ended semester invite shows error."""
        url = reverse(
            "reg:add-student", kwargs={"invite_id": self.ended_semester_invite.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/student_invite_expired.html")
        self.assertContains(response, "semester has ended")

    def test_post_login_choice_yes(self):
        """Test POST request to choose 'yes' redirects to login."""
        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"has_account": "yes"})
        self.assertEqual(response.status_code, 302)
        # Should redirect to login with next parameter
        self.assertIn("/accounts/login/", response.url)
        self.assertIn("next=", response.url)

    def test_post_login_choice_no(self):
        """Test POST request to choose 'no' shows registration form."""
        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"has_account": "no"})
        self.assertEqual(response.status_code, 302)  # Redirect
        # Check session has creating_new_account flag
        session = self.client.session
        self.assertTrue(session["creating_new_account"])

    def test_get_registration_form(self):
        """Test GET request shows registration form when creating new account."""
        # Set session
        session = self.client.session
        session["creating_new_account"] = True
        session.save()

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/student_register.html")

    def test_post_registration_creates_user(self):
        """Test POST request creates user and redirects to student selection."""
        # Set session
        session = self.client.session
        session["creating_new_account"] = True
        session.save()

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(
            url,
            {
                "username": "alicejohnson",
                "password1": "testpass123!@#",
                "password2": "testpass123!@#",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirect

        # Check user was created
        user = User.objects.get(username="alicejohnson")
        self.assertIsNotNone(user)

        # Check user is logged in
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, "alicejohnson")

        # Check session flag is cleared
        session = self.client.session
        self.assertNotIn("creating_new_account", session)

    def test_get_student_selection_as_logged_in_user(self):
        """Test GET request shows student selection when logged in."""
        # Create and login a new user
        User.objects.create_user(username="newuser", password="testpass123")
        self.client.login(username="newuser", password="testpass123")

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/select_student.html")
        self.assertContains(response, "Alice Johnson")
        # Bob Smith should not appear because they're already linked
        self.assertNotContains(response, "Bob Smith")

    def test_post_student_selection(self):
        """Test POST request to select student links user to student."""
        # Create and login a new user
        user = User.objects.create_user(username="newuser", password="testpass123")
        self.client.login(username="newuser", password="testpass123")

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"student": self.student1.id})
        self.assertEqual(response.status_code, 302)  # Redirect to home

        # Check student is linked to user
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.user, user)

    def test_post_student_selection_already_taken(self):
        """Test POST request to select already taken student shows error."""
        # Create and login a new user
        User.objects.create_user(username="newuser", password="testpass123")
        self.client.login(username="newuser", password="testpass123")

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(url, {"student": self.student2.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/student_already_taken.html")
        self.assertContains(response, "Bob Smith")

    def test_get_already_registered_student(self):
        """Test GET request when user already has student for this semester."""
        # Login with existing user who already has a student
        self.client.login(username="bobsmith", password="testpass123")

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/student_already_registered.html")
        self.assertContains(response, "Bob Smith")

    def test_get_no_students_available(self):
        """Test GET request when no students are available."""
        # Link all students to users
        user1 = User.objects.create_user(username="user1", password="testpass123")
        self.student1.user = user1
        self.student1.save()

        # Create and login a new user
        User.objects.create_user(username="user2", password="testpass123")
        self.client.login(username="user2", password="testpass123")

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/no_students_available.html")

    def test_post_registration_invalid_form(self):
        """Test POST request with invalid form shows errors."""
        # Set session
        session = self.client.session
        session["creating_new_account"] = True
        session.save()

        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})
        response = self.client.post(
            url,
            {
                "username": "alicejohnson",
                "password1": "testpass123!@#",
                "password2": "differentpass",  # Passwords don't match
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/student_register.html")
        # User should not be created
        self.assertFalse(User.objects.filter(username="alicejohnson").exists())

    def test_existing_user_login_flow(self):
        """Test that existing users can login and select student."""
        # Create a user without a student for this semester
        user = User.objects.create_user(username="existinguser", password="testpass123")

        # Get the invite URL
        url = reverse("reg:add-student", kwargs={"invite_id": self.valid_invite.id})

        # First, choose "yes" (has account)
        response = self.client.post(url, {"has_account": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

        # Login
        self.client.login(username="existinguser", password="testpass123")

        # Now access the invite link again
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "reg/select_student.html")

        # Select a student
        response = self.client.post(url, {"student": self.student1.id})
        self.assertEqual(response.status_code, 302)

        # Check student is linked
        self.student1.refresh_from_db()
        self.assertEqual(self.student1.user, user)


class StudentInviteLinkAdminTest(TestCase):
    """Tests for the StudentInviteLink admin."""

    def setUp(self):
        """Set up test data."""
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@example.com",
        )
        self.client.login(username="admin", password="admin123")

        # Create semester
        self.semester = Semester.objects.create(
            name="Fall 2025",
            slug="fall-2025",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
        )

    def test_admin_list_display(self):
        """Test that admin list page works."""
        url = reverse("admin:reg_studentinvitelink_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_admin_create_invite(self):
        """Test creating invite link through admin."""
        url = reverse("admin:reg_studentinvitelink_add")
        response = self.client.post(
            url,
            {
                "name": "New Student Invite",
                "semester": self.semester.id,
                "expiration_date_0": "2025-12-31",  # Date part
                "expiration_date_1": "23:59:59",  # Time part
            },
        )
        # Should redirect to changelist on success
        self.assertEqual(response.status_code, 302)

        # Check invite was created
        invite = StudentInviteLink.objects.get(name="New Student Invite")
        self.assertIsNotNone(invite)
        self.assertEqual(invite.semester, self.semester)

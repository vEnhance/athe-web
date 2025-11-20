from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ApplyPSet


class ApplyPSetModelTests(TestCase):
    """Tests for the ApplyPSet model."""

    def setUp(self):
        """Set up test data."""
        self.test_file = SimpleUploadedFile(
            "test.pdf", b"file_content", content_type="application/pdf"
        )

    def test_create_apply_pset(self):
        """Test creating an ApplyPSet."""
        pset = ApplyPSet.objects.create(
            name="Fall 2025 PSet",
            deadline=timezone.now() + timedelta(days=30),
            status="active",
            file=self.test_file,
            instructions="Apply by filling out the form.",
            closed_message="Applications closed!",
        )
        self.assertEqual(pset.name, "Fall 2025 PSet")
        self.assertEqual(pset.status, "active")
        self.assertIsNotNone(pset.file)

    def test_apply_pset_ordering(self):
        """Test that ApplyPSets are ordered by deadline descending."""
        _pset1 = ApplyPSet.objects.create(
            name="PSet 1",
            deadline=timezone.now() + timedelta(days=10),
            status="active",
            file=SimpleUploadedFile("test1.pdf", b"content"),
            instructions="Test",
            closed_message="Closed",
        )
        _pset2 = ApplyPSet.objects.create(
            name="PSet 2",
            deadline=timezone.now() + timedelta(days=20),
            status="active",
            file=SimpleUploadedFile("test2.pdf", b"content"),
            instructions="Test",
            closed_message="Closed",
        )
        psets = list(ApplyPSet.objects.all())
        self.assertEqual(psets[0].name, "PSet 2")
        self.assertEqual(psets[1].name, "PSet 1")

    def test_apply_pset_str(self):
        """Test the string representation of ApplyPSet."""
        pset = ApplyPSet.objects.create(
            name="Test PSet",
            deadline=timezone.now(),
            status="draft",
            file=self.test_file,
            instructions="Test",
            closed_message="Closed",
        )
        self.assertEqual(str(pset), "Test PSet")


class ApplyViewTests(TestCase):
    """Tests for the ApplyView."""

    def test_apply_view_with_active_psets(self):
        """Test ApplyView displays active problem sets."""
        _pset = ApplyPSet.objects.create(
            name="Active PSet",
            deadline=timezone.now() + timedelta(days=30),
            status="active",
            file=SimpleUploadedFile("test.pdf", b"content"),
            instructions="These are the instructions.",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active PSet")
        self.assertContains(response, "These are the instructions.")

    def test_apply_view_with_no_active_shows_closed_message(self):
        """Test ApplyView shows closed message when no active psets."""
        _pset = ApplyPSet.objects.create(
            name="Completed PSet",
            deadline=timezone.now() - timedelta(days=10),
            status="completed",
            file=SimpleUploadedFile("test.pdf", b"content"),
            instructions="Instructions",
            closed_message="Applications are closed for now.",
        )
        response = self.client.get(reverse("home:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Applications are closed for now.")
        self.assertNotContains(response, "Completed PSet")

    def test_apply_view_with_no_psets_at_all(self):
        """Test ApplyView shows generic message when no psets exist."""
        response = self.client.get(reverse("home:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing here yet, check back later!")

    def test_apply_view_does_not_show_draft_psets(self):
        """Test ApplyView does not display draft problem sets."""
        _pset = ApplyPSet.objects.create(
            name="Draft PSet",
            deadline=timezone.now() + timedelta(days=30),
            status="draft",
            file=SimpleUploadedFile("test.pdf", b"content"),
            instructions="Draft instructions",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Draft PSet")
        self.assertContains(response, "Nothing here yet, check back later!")

    def test_apply_view_shows_multiple_active_psets(self):
        """Test ApplyView displays all active problem sets."""
        _pset1 = ApplyPSet.objects.create(
            name="Active PSet 1",
            deadline=timezone.now() + timedelta(days=20),
            status="active",
            file=SimpleUploadedFile("test1.pdf", b"content"),
            instructions="Instructions 1",
            closed_message="Closed",
        )
        _pset2 = ApplyPSet.objects.create(
            name="Active PSet 2",
            deadline=timezone.now() + timedelta(days=30),
            status="active",
            file=SimpleUploadedFile("test2.pdf", b"content"),
            instructions="Instructions 2",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active PSet 1")
        self.assertContains(response, "Active PSet 2")

    def test_apply_view_shows_most_recent_completed_message(self):
        """Test ApplyView shows closed message from most recent completed pset."""
        _old_pset = ApplyPSet.objects.create(
            name="Old PSet",
            deadline=timezone.now() - timedelta(days=60),
            status="completed",
            file=SimpleUploadedFile("old.pdf", b"content"),
            instructions="Old instructions",
            closed_message="Old closed message",
        )
        _recent_pset = ApplyPSet.objects.create(
            name="Recent PSet",
            deadline=timezone.now() - timedelta(days=10),
            status="completed",
            file=SimpleUploadedFile("recent.pdf", b"content"),
            instructions="Recent instructions",
            closed_message="Recent closed message",
        )
        response = self.client.get(reverse("home:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent closed message")
        self.assertNotContains(response, "Old closed message")


class PastPsetsViewTests(TestCase):
    """Tests for the PastPsetsView."""

    def test_past_psets_view_shows_completed_psets(self):
        """Test PastPsetsView displays completed problem sets."""
        _pset = ApplyPSet.objects.create(
            name="Completed PSet",
            deadline=timezone.now() - timedelta(days=30),
            status="completed",
            file=SimpleUploadedFile("test.pdf", b"content"),
            instructions="Instructions",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:past_psets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed PSet")

    def test_past_psets_view_does_not_show_active_psets(self):
        """Test PastPsetsView does not display active problem sets."""
        _pset = ApplyPSet.objects.create(
            name="Active PSet",
            deadline=timezone.now() + timedelta(days=30),
            status="active",
            file=SimpleUploadedFile("test.pdf", b"content"),
            instructions="Instructions",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:past_psets"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Active PSet")

    def test_past_psets_view_does_not_show_draft_psets(self):
        """Test PastPsetsView does not display draft problem sets."""
        _pset = ApplyPSet.objects.create(
            name="Draft PSet",
            deadline=timezone.now() + timedelta(days=30),
            status="draft",
            file=SimpleUploadedFile("test.pdf", b"content"),
            instructions="Instructions",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:past_psets"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Draft PSet")

    def test_past_psets_view_with_no_completed_psets(self):
        """Test PastPsetsView shows message when no completed psets exist."""
        response = self.client.get(reverse("home:past_psets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No past problem sets available yet.")

    def test_past_psets_view_reverse_chronological_order(self):
        """Test PastPsetsView lists psets in reverse chronological order."""
        _pset1 = ApplyPSet.objects.create(
            name="Old PSet",
            deadline=timezone.now() - timedelta(days=60),
            status="completed",
            file=SimpleUploadedFile("old.pdf", b"content"),
            instructions="Old",
            closed_message="Closed",
        )
        _pset2 = ApplyPSet.objects.create(
            name="Recent PSet",
            deadline=timezone.now() - timedelta(days=10),
            status="completed",
            file=SimpleUploadedFile("recent.pdf", b"content"),
            instructions="Recent",
            closed_message="Closed",
        )
        response = self.client.get(reverse("home:past_psets"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        recent_pos = content.find("Recent PSet")
        old_pos = content.find("Old PSet")
        self.assertLess(
            recent_pos, old_pos, "Recent PSet should appear before Old PSet"
        )

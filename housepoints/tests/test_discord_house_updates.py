from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award


# ============================================================================
# send_discord_house_updates Management Command Tests
# ============================================================================


@pytest.mark.django_db
def test_discord_house_updates_missing_env_var():
    """Test that missing DISCORD_HOUSE_POINTS_WEBHOOK env var causes exit 1."""
    out = StringIO()
    err = StringIO()

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            call_command("send_discord_house_updates", stdout=out, stderr=err)

    assert exc_info.value.code == 1
    assert "DISCORD_HOUSE_POINTS_WEBHOOK" in err.getvalue()


@pytest.mark.django_db
def test_discord_house_updates_no_active_semester():
    """Test that no active semester causes exit 1."""
    # Create a semester that's not active (in the past)
    Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=180)).date(),
        end_date=(timezone.now() - timedelta(days=90)).date(),
    )

    out = StringIO()
    err = StringIO()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        call_command("send_discord_house_updates", stdout=out, stderr=err)

    assert "No active semester" in err.getvalue()


@pytest.mark.django_db
def test_discord_house_updates_multiple_active_semesters():
    """Test that multiple active semesters cause exit 1."""
    today = timezone.now().date()

    # Create two overlapping active semesters
    Semester.objects.create(
        name="Semester 1",
        slug="sem1",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
    )
    Semester.objects.create(
        name="Semester 2",
        slug="sem2",
        start_date=today - timedelta(days=15),
        end_date=today + timedelta(days=45),
    )

    out = StringIO()
    err = StringIO()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        with pytest.raises(SystemExit) as exc_info:
            call_command("send_discord_house_updates", stdout=out, stderr=err)

    assert exc_info.value.code == 1
    assert "Multiple active semesters" in err.getvalue()


@pytest.mark.django_db
def test_discord_house_updates_frozen_leaderboard():
    """Test that frozen leaderboard prints warning and exits 0."""
    today = timezone.now().date()
    freeze_time = timezone.now() - timedelta(days=1)

    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
        house_points_freeze_date=freeze_time,
    )

    out = StringIO()
    err = StringIO()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        # Should not raise - exit 0
        call_command("send_discord_house_updates", stdout=out, stderr=err)

    assert "frozen" in out.getvalue().lower()
    assert "No update sent" in out.getvalue()


@pytest.mark.django_db
def test_discord_house_updates_sends_message():
    """Test that message is sent to Discord with correct content."""
    today = timezone.now().date()

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
    )

    # Create students and awards
    student1 = Student.objects.create(
        airtable_name="Student 1",
        semester=semester,
        house=Student.House.OWL,
    )
    student2 = Student.objects.create(
        airtable_name="Student 2",
        semester=semester,
        house=Student.House.CAT,
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=10,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    out = StringIO()
    err = StringIO()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com/webhook"}
    ):
        with patch("requests.post", return_value=mock_response) as mock_post:
            call_command("send_discord_house_updates", stdout=out, stderr=err)

    # Verify requests.post was called
    assert mock_post.called
    call_args = mock_post.call_args

    # Check the webhook URL
    assert call_args[0][0] == "https://example.com/webhook"

    # Check the message content
    message_content = call_args[1]["json"]["content"]

    # Should contain the role mention
    assert "<@&1345991464831811665>" in message_content

    # Should contain owl and cat emojis with scores
    assert ":owlheart:" in message_content
    assert "10" in message_content
    assert ":catlove:" in message_content
    assert "5" in message_content

    # Should contain the links
    assert "https://beta.athemath.org/house-points/" in message_content
    assert "https://beta.athemath.org/house-points/awards/my/" in message_content

    # Success message
    assert "Successfully sent" in out.getvalue()


@pytest.mark.django_db
def test_discord_house_updates_sorted_by_score():
    """Test that houses are sorted from highest to lowest score."""
    today = timezone.now().date()

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
    )

    # Create students in all houses with different scores
    houses_and_scores = [
        (Student.House.BUNNY, 100),
        (Student.House.OWL, 50),
        (Student.House.CAT, 75),
        (Student.House.BLOB, 25),
        (Student.House.RED_PANDA, 60),
    ]

    for house, points in houses_and_scores:
        student = Student.objects.create(
            airtable_name=f"Student {house}",
            semester=semester,
            house=house,
        )
        Award.objects.create(
            semester=semester,
            student=student,
            award_type=Award.AwardType.STAFF_BONUS,
            points=points,
        )

    out = StringIO()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        with patch("requests.post", return_value=mock_response) as mock_post:
            call_command("send_discord_house_updates", stdout=out)

    message_content = mock_post.call_args[1]["json"]["content"]
    lines = message_content.split("\n")

    # Find the lines with scores (after role mention, before empty line)
    score_lines = []
    for line in lines[1:]:  # Skip role mention
        if line.strip() == "":
            break
        score_lines.append(line)

    # Extract scores in order
    scores = []
    for line in score_lines:
        # Each line is like ":emoji: SCORE"
        parts = line.split()
        scores.append(int(parts[2]))

    # Verify scores are in descending order
    assert scores == sorted(scores, reverse=True)
    assert scores == [100, 75, 60, 50, 25]


@pytest.mark.django_db
def test_discord_house_updates_includes_zero_point_houses():
    """Test that houses with 0 points are included."""
    today = timezone.now().date()

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
    )

    # Only give points to one house
    student = Student.objects.create(
        airtable_name="Student 1",
        semester=semester,
        house=Student.House.OWL,
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=10,
    )

    out = StringIO()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        with patch("requests.post", return_value=mock_response) as mock_post:
            call_command("send_discord_house_updates", stdout=out)

    message_content = mock_post.call_args[1]["json"]["content"]

    # All 5 houses should be in the message
    assert ":owlheart:" in message_content
    assert ":blobheart:" in message_content
    assert ":redpandaheart:" in message_content
    assert ":catlove:" in message_content
    assert ":bunnylove:" in message_content

    # Should have five "0" entries (for houses with no points)
    # Count occurrences of " 0" (space before 0 to avoid matching "10")
    assert message_content.count(" 0 points") == 4  # 4 houses with 0 points


@pytest.mark.django_db
def test_discord_house_updates_webhook_failure():
    """Test that webhook failure causes exit 1."""
    import requests

    today = timezone.now().date()

    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
    )

    out = StringIO()
    err = StringIO()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        with patch(
            "requests.post",
            side_effect=requests.exceptions.RequestException("Network error"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                call_command("send_discord_house_updates", stdout=out, stderr=err)

    assert exc_info.value.code == 1
    assert "Failed to send" in err.getvalue()


@pytest.mark.django_db
def test_discord_house_updates_empty_semester():
    """Test message is sent even when there are no awards."""
    today = timezone.now().date()

    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=30),
    )

    out = StringIO()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch.dict(
        "os.environ", {"DISCORD_HOUSE_POINTS_WEBHOOK": "https://example.com"}
    ):
        with patch("requests.post", return_value=mock_response) as mock_post:
            call_command("send_discord_house_updates", stdout=out)

    # Should still send a message with all 0s
    assert mock_post.called
    message_content = mock_post.call_args[1]["json"]["content"]

    # All houses should show 0
    assert message_content.count(" 0 points") == 5

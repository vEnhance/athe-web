import pytest
from django.test import RequestFactory

from weblog.models import HistoryEntry
from weblog.views import HistoryListView


@pytest.mark.django_db
def test_history_list_view_empty():
    """Test HistoryListView with no entries."""
    factory = RequestFactory()
    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_history_list_view_with_visible_entries():
    """Test HistoryListView shows visible entries."""
    factory = RequestFactory()

    # Create visible entries
    entry1 = HistoryEntry.objects.create(
        title="First Entry",
        slug="first-entry",
        content="First content.",
        visible=True,
    )
    entry2 = HistoryEntry.objects.create(
        title="Second Entry",
        slug="second-entry",
        content="Second content.",
        visible=True,
    )

    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    assert response.status_code == 200
    assert response.context_data["history_entries"].count() == 2

    # Render to get content
    response.render()
    content = response.content.decode()
    assert entry1.title in content
    assert entry2.title in content


@pytest.mark.django_db
def test_history_list_view_excludes_invisible():
    """Test that HistoryListView excludes invisible entries."""
    factory = RequestFactory()

    # Create one visible and one invisible entry
    visible_entry = HistoryEntry.objects.create(
        title="Visible Entry",
        slug="visible-entry",
        content="Visible content.",
        visible=True,
    )
    invisible_entry = HistoryEntry.objects.create(
        title="Invisible Entry",
        slug="invisible-entry",
        content="Hidden content.",
        visible=False,
    )

    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    assert response.status_code == 200
    entries = response.context_data["history_entries"]
    assert entries.count() == 1

    # Render to get content
    response.render()
    content = response.content.decode()
    assert visible_entry.title in content
    assert invisible_entry.title not in content


@pytest.mark.django_db
def test_history_list_view_ordering():
    """Test that HistoryListView shows entries in reverse chronological order."""
    factory = RequestFactory()

    # Create entries
    entry1 = HistoryEntry.objects.create(
        title="Older Entry",
        slug="older-entry",
        content="Older content.",
        visible=True,
    )
    entry2 = HistoryEntry.objects.create(
        title="Newer Entry",
        slug="newer-entry",
        content="Newer content.",
        visible=True,
    )

    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    assert response.status_code == 200
    entries = list(response.context_data["history_entries"])
    assert entries[0].id == entry2.id
    assert entries[1].id == entry1.id


@pytest.mark.django_db
def test_history_list_view_no_login_required():
    """Test that HistoryListView is accessible without authentication."""
    factory = RequestFactory()

    # Create an entry so we have something to show
    HistoryEntry.objects.create(
        title="Public Entry",
        slug="public-entry",
        content="Public content.",
        visible=True,
    )

    # Request without any user authentication
    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    # Should be accessible without login
    assert response.status_code == 200


@pytest.mark.django_db
def test_history_list_view_all_invisible():
    """Test HistoryListView when all entries are invisible."""
    factory = RequestFactory()

    # Create only invisible entries
    HistoryEntry.objects.create(
        title="Hidden 1",
        slug="hidden-1",
        content="Hidden content 1.",
        visible=False,
    )
    HistoryEntry.objects.create(
        title="Hidden 2",
        slug="hidden-2",
        content="Hidden content 2.",
        visible=False,
    )

    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    assert response.status_code == 200
    entries = response.context_data["history_entries"]
    assert entries.count() == 0


@pytest.mark.django_db
def test_history_list_view_mixed_visibility():
    """Test HistoryListView with mixed visibility entries."""
    factory = RequestFactory()

    # Create mix of visible and invisible entries
    visible1 = HistoryEntry.objects.create(
        title="Visible 1",
        slug="visible-1",
        content="Visible content 1.",
        visible=True,
    )
    HistoryEntry.objects.create(
        title="Invisible",
        slug="invisible",
        content="Invisible content.",
        visible=False,
    )
    visible2 = HistoryEntry.objects.create(
        title="Visible 2",
        slug="visible-2",
        content="Visible content 2.",
        visible=True,
    )

    request = factory.get("/history/")
    response = HistoryListView.as_view()(request)

    assert response.status_code == 200
    entries = list(response.context_data["history_entries"])
    assert len(entries) == 2

    entry_titles = [e.title for e in entries]
    assert visible1.title in entry_titles
    assert visible2.title in entry_titles
    assert "Invisible" not in entry_titles

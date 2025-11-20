from django.views.generic import ListView

from .models import HistoryEntry


class HistoryListView(ListView):
    """ListView for HistoryEntry with table of contents."""

    model = HistoryEntry
    template_name = "weblog/history_list.html"
    context_object_name = "history_entries"

    def get_queryset(self):  # type: ignore
        """Return only visible history entries in reverse chronological order."""
        return HistoryEntry.objects.filter(visible=True)

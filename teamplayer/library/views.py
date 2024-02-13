import json
import os

from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from haystack.generic_views import SearchView
from haystack.query import SearchQuerySet

from teamplayer.lib.websocket import IPCHandler
from teamplayer.library.forms import AddToQueueForm
from teamplayer.models import LibraryItem
from teamplayer.serializers import EntrySerializer


@login_required
@require_POST
def add_to_queue(request: HttpRequest) -> HttpResponse:
    """Add song to the queue.

    Return the dictified entry on success.  Or {'error': message} on failure.
    """
    station = request.station  # type: ignore[attr-defined]
    form = AddToQueueForm(request.POST)
    if form.is_valid():
        library_id = form.cleaned_data["song_id"]

        library_item = get_object_or_404(LibraryItem, pk=library_id)

        if not os.path.exists(library_item.filename):
            return HttpResponse(
                json.dumps({"error": "Song could not be located"}),
                content_type="application/json",
            )

        with open(library_item.filename, "rb") as fp:
            entry = request.player.queue.add_song(File(fp), station)  # type: ignore[attr-defined]

        # notify the Spin Doctor
        IPCHandler.send_message("song_added", entry.pk)

        return HttpResponse(
            json.dumps(EntrySerializer(entry).data), content_type="application/json"
        )

    return HttpResponse(
        json.dumps({"error": form.errors.as_text()}), content_type="application/json"
    )


class SongSearchView(SearchView):
    queryset = SearchQuerySet()
    template_name = "search/search.html"

    def get_context_data(self, *args, **kwargs):
        context = super(SongSearchView, self).get_context_data(*args, **kwargs)
        request = self.request
        station_id = request.session.get("station_id")
        context["station_id"] = station_id

        return context


song_search = SongSearchView.as_view()

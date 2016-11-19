import json
import os

from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from haystack.generic_views import SearchView
from haystack.query import SearchQuerySet

from teamplayer.lib.websocket import IPCHandler
from teamplayer.serializers import EntrySerializer
from tp_library.forms import AddToQueueForm
from tp_library.models import SongFile


@login_required
@require_POST
def add_to_queue(request):
    """Add song to the queue.

    Return the dictified entry on success.  Or {'error', message} on failure.
    """
    station = request.station
    form = AddToQueueForm(request.POST)
    if form.is_valid():
        songfile_id = form.cleaned_data['song_id']

        songfile = get_object_or_404(SongFile, pk=songfile_id)

        if not os.path.exists(songfile.filename):
            return HttpResponse(
                json.dumps({'error': 'Song could not be located'}),
                content_type='application/json'
            )

        fp = File(open(songfile.filename, 'rb'))

        entry = request.player.queue.add_song(fp, station)

        # notify the Spin Doctor
        IPCHandler.send_message('song_added', entry.pk)

        return HttpResponse(
            json.dumps(EntrySerializer(entry).data),
            content_type='application/json'
        )

    return HttpResponse(
        json.dumps({'error': form.errors.as_text()}),
        content_type='application/json'
    )


class SongSearchView(SearchView):
    queryset = SearchQuerySet()
    template_name = 'search/search.html'

    def get_context_data(self, *args, **kwargs):
        context = super(SongSearchView, self).get_context_data(*args, **kwargs)
        request = self.request
        station_id = request.session.get('station_id')
        context['station_id'] = station_id

        return context

song_search = SongSearchView.as_view()

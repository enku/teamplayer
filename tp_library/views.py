import json
import os

from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import get_current_site
from django.contrib.syndication.views import Feed, add_domain
from django.core.files import File
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from haystack.views import SearchView, search_view_factory

from teamplayer.lib.websocket import IPCHandler
from teamplayer.models import Station
from teamplayer.views import get_station_from_session
from teamplayer.serializers import EntrySerializer
from tp_library.models import SongFile
from tp_library.forms import AddToQueueForm


@login_required
@require_POST
def add_to_queue(request):
    """Add song to the queue.

    Return the dictified entry on success.  Or {'error', message} on failure.
    """
    station = get_station_from_session(request)
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
    def extra_context(self):
        request = self.request
        station_id = request.session.get('station_id')

        return {
            'station_id': station_id,
        }

song_search = search_view_factory(SongSearchView)


def get_song(request, song_id):
    song = get_object_or_404(SongFile, pk=song_id)
    return HttpResponse(open(song.filename), content_type=song.mimetype)


class LibraryFeed(Feed):
    items_per_feed = 100

    def get_object(self, request, station_id):
        # note, i need to store the request because item_enclosure_url needs to
        # return a full url, and the only way to do that is if we have the
        # the request.
        self.request = request
        return get_object_or_404(Station, pk=station_id)

    def items(self, obj):
        return (SongFile.objects
                .filter(station_id=obj.pk)
                .order_by('-date_added')[:self.items_per_feed])

    def title(self, obj):
        return obj.name

    def link(self, obj):
        return reverse('teamplayer.views.home', args=[obj.pk])

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return str(item)

    def author_name(self, obj):
        return obj.creator.username

    def item_author_name(self, item):
        return item.added_by.username

    def item_enclosure_url(self, item):
        request = self.request
        current_site = get_current_site(request)

        link = item.get_absolute_url()
        link = add_domain(current_site.domain, link, request.is_secure())
        return link

    def item_enclosure_length(self, item):
        return item.filesize

    def item_enclosure_mime_type(self, item):
        return item.mimetype

    def item_categories(self, item):
        return [item.genre]

feed = LibraryFeed()

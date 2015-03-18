"""
Views for the teamplayer django app
"""
import json
from urllib.parse import quote_plus

import django
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.files import File
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response

from teamplayer import version_string
from teamplayer.conf import settings
from teamplayer.forms import (
    ChangeDJNameForm,
    CreateStationForm,
    EditStationForm
)
from teamplayer.lib import mktemp_file_from_request, songs
from teamplayer.lib.mpc import MPC
from teamplayer.lib.websocket import IPCHandler
from teamplayer.models import Entry, Player, Station
from teamplayer.serializers import (
    EntrySerializer,
    PlayerSerializer,
    StationSerializer
)
from tp_library.models import SongFile


class HttpResponseNoContent(HttpResponse):

    """HTTP 204 response"""
    status_code = 204


def get_mpd_url(request, station):
    http_host = request.META.get('HTTP_HOST', 'localhost')
    http_host = http_host.partition(':')[0]
    station = request.station
    station_id = station.pk
    port = settings.HTTP_PORT + station_id
    return 'http://{0}:{1}/mpd.mp3'.format(http_host, port)


def get_websocket_url(request):
    http_host = request.META.get('HTTP_HOST', 'localhost')
    http_host = http_host.partition(':')[0]
    return 'ws://{0}:{1}/'.format(http_host, settings.WEBSOCKET_PORT)


@login_required
def home(request, station_id=None):
    """This is the main page view for the teamplayer app"""

    station_id = station_id or request.session.get('station_id', None)

    if station_id is None:
        return redirect_to_home(request)
    else:
        try:
            station = Station.objects.get(pk=station_id)
        except Station.DoesNotExist:
            return redirect_to_home(request)

    request.session['station_id'] = station.pk

    if request.is_ajax():
        serializer = StationSerializer(station, context={'request': request})
        return HttpResponse(json.dumps(serializer.data),
                            content_type='application/json')

    return render(
        request,
        'teamplayer/home.html',
        {
            'mpd_url': get_mpd_url(request, station),
            'name': request.player.dj_name or 'Anonymous',
            'station': station,
            'home': Station.main_station().pk,
            'stations': Station.get_stations(),
            'username': request.player.username,
        },
    )


def register(request):
    return render(request, 'teamplayer/home.html', {'register': True})


@api_view(['GET'])
@login_required
def show_queue(request):
    """
    View to display the titles in the player's queue.
    """
    station = request.station

    entries = request.player.queue.entry_set.filter(station=station)
    seralizer = EntrySerializer(entries, many=True)
    return Response(seralizer.data)


@api_view(['GET', 'DELETE'])
@login_required
def show_entry(request, entry_id):
    """
    View to show an entry
    """
    entry = get_object_or_404(Entry, pk=entry_id, queue__player=request.player)
    data = EntrySerializer(entry).data
    entry_id = entry.pk
    if request.method == 'DELETE':
        entry.song.delete()
        entry.delete()
        IPCHandler.send_message('song_removed', entry_id)
    return Response(data)


@api_view(['GET'])
@login_required
def show_players(request):
    """view to show player stats/settings"""
    players = Player.objects.all()
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@login_required
@require_POST
def add_to_queue(request):
    """
    Add song to the queue
    """
    station = request.station

    if request.FILES:
        uploaded_file = next(request.FILES.values())
    else:
        uploaded_file = File(mktemp_file_from_request(request))

    try:
        entry = request.player.queue.add_song(uploaded_file, station)
    except songs.SongMetadataError:
        client_filename = request.FILES['files[]'].name
        if client_filename:
            extra = '%s: ' % client_filename
        else:
            extra = ''
        status = {'fail': ('%sThe song was not added because I did '
                           'not recognize the type of file you sent' % extra)
                  }
        return HttpResponse(json.dumps(status),
                            content_type='application/json')

    # notify the Spin Doctor
    IPCHandler.send_message('song_added', entry.pk)

    if settings.UPLOADED_LIBRARY_DIR:
        IPCHandler.send_message('library_add', entry.pk)

    return HttpResponse(json.dumps(EntrySerializer(entry).data),
                        content_type='application/json')


@login_required
def randomize_queue(request):
    """Randomize the player's queue"""
    station = request.station
    request.player.queue.randomize(station)
    return redirect(reverse('teamplayer.views.show_queue'))


@login_required
def order_by_rank(request):
    """Order your queue according to artist rank"""
    station = request.station
    request.player.queue.order_by_rank(station)
    return redirect(reverse('teamplayer.views.show_queue'))


@login_required
@require_POST
def toggle_queue_status(request):
    """Toggle player's queue's active status"""
    new_status = bool(request.player.queue.toggle_status())
    IPCHandler.send_message(
        'queue_status',
        {'user': request.player.username, 'status': new_status}
    )
    return HttpResponse(json.dumps(new_status), content_type='application/json')


@login_required
@require_POST
def toggle_auto_mode(request):
    """Toggle player's auto_mode flag"""
    request.player.toggle_auto_mode()
    return HttpResponseNoContent()


def currently_playing(request):
    """
    Return the following as a json dict

    dj
    artist
    title
    total_time
    remaining_time
    artist_image
    """
    station = request.station

    output = MPC(station=station).currently_playing()
    response = HttpResponse(json.dumps(output),
                            content_type='application/json')
    if output['remaining_time'] is not None:
        response['Cache-Control'] = 'no-cache, max-age={0}'.format(
            output['remaining_time'])
    else:
        response['Cache-Control'] = 'no-cache, max-age=60'
    return response


@login_required
@require_POST
@transaction.atomic
def reorder_queue(request):
    """
    Given comma-delimited string (of integers), re-order queue
    return the re-ordered list of ids in json format
    """
    queue = request.player.queue
    new_order = request.body.decode('utf-8').split(',')
    new_order = [int(i) for i in new_order]
    ids = [i['id'] for i in queue.reorder(new_order)]

    return HttpResponse(
        json.dumps(ids),
        content_type='application/json'
    )


@login_required()
@require_POST
def change_dj_name(request):
    """Change player's "dj name" according to dj_name field"""
    form = ChangeDJNameForm(request.POST, player=request.player)

    if not form.is_valid():
        return HttpResponse(form.errors.values()[0])

    previous_dj_name = request.player.dj_name
    request.player.set_dj_name(form.cleaned_data['dj_name'])

    # send a notification the the spin doctor
    IPCHandler.send_message(
        message_type='dj_name_change',
        data={
            'user_id': request.player.pk,
            'previous_dj_name': previous_dj_name,
            'dj_name': form.cleaned_data['dj_name'],
        }
    )
    return HttpResponseNoContent('')


def logout(request):
    """Log out the player from TP"""
    auth_logout(request)
    messages.info(request, 'Thanks for playing.')
    return HttpResponseRedirect(reverse('django.contrib.auth.views.login'))


def registration(request):
    """The view that handles the actual registration form"""
    context = dict()
    context['form'] = UserCreationForm()

    if request.method == "POST":
        context['form'] = form = UserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            try:
                Player.objects.get(user__username=username)
                context['error'] = 'User "%s" already exists.' % username
            except Player.DoesNotExist:
                player = Player.objects.create_player(username=username,
                                                      password=password)
                IPCHandler.send_message(
                    'user_created', PlayerSerializer(player).data)
                messages.info(request, '%s registered. Please login.' %
                              username)
                return HttpResponse('<script>window.location="%s"</script>' %
                                    reverse('teamplayer.views.home'))

    context['users'] = Player.objects.all()
    return render(request, 'teamplayer/register.html', context)


def artist_page(_request, artist):
    """Simply redirect to last.fm link for <<artist>>"""
    return HttpResponseRedirect(
        'http://last.fm/music/' + quote_plus(artist.encode('utf-8'))
    )


def artist_image(_request, artist):
    """Return a permanent redirect for last.fm image for artist"""
    return HttpResponseRedirect(
        songs.get_image_url_for(artist)
    )


@api_view(['GET'])
def show_stations(request):
    stations = Station.get_stations()
    serializer = StationSerializer(
        stations, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
def station_detail(request, station_id):
    if station_id == 'mine':
        station = get_object_or_404(Station, creator=request.player)
    else:
        station = get_object_or_404(Station, pk=station_id)
    serializer = StationSerializer(station, context={'request': request})
    return Response(serializer.data)


def previous_station(request):
    """Redirect to the previous station"""
    station = request.station
    stations = Station.get_stations().order_by('pk').values_list('pk',
                                                                 flat=True)
    stations = list(stations)

    station_id = station.pk if station else 0
    try:
        index = stations.index(station_id)
    except IndexError:
        index = 0

    previous_id = stations[index - 1] if index else stations[-1]
    request.session['station_id'] = previous_id
    return redirect(reverse('station', args=(previous_id,)))


def next_station(request):
    """Redirect to the next station"""
    station = request.station
    stations = Station.get_stations().order_by('pk').values_list('pk',
                                                                 flat=True)
    stations = list(stations)

    station_id = station.pk if station else 0
    try:
        index = stations.index(station_id)
    except IndexError:
        index = 0

    next_index = index + 1 if len(stations) >= index + 2 else 0
    next_id = stations[next_index]
    request.session['station_id'] = next_id
    return redirect(reverse('station', args=(next_id,)))


@login_required
@require_POST
def edit_station(request):
    main_station = Station.main_station()
    message = ''
    form = EditStationForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data['name']
        station_id = form.cleaned_data['station_id']
        action = form.cleaned_data['action']

        station = get_object_or_404(Station, pk=station_id,
                                    creator=request.player)
        if action == 'rename':
            station.name = name
            station.save()
            IPCHandler.send_message('station_rename', [station_id, name])
        elif action == 'remove':
            station.delete()
            if request.session['station_id'] == station_id:
                request.session['station_id'] = main_station.pk
            IPCHandler.send_message('station_delete', station_id)
    else:
        message = '\n'.join([i[0] for i in form.errors.values()])

    return HttpResponse(message)


@login_required
@require_POST
def create_station(request):
    form = CreateStationForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data['name']

        station = Station.create_station(name, request.player)
        IPCHandler.send_message('station_create', station.pk)
        return HttpResponseNoContent()
    return HttpResponse('Error creating station', content_type='text/plain')


def about(request):
    """about/copyright page"""
    query = SongFile.objects.aggregate(Count('title'), Sum('filesize'))

    return render(
        request,
        'teamplayer/about.html',
        {
            'version': version_string(),
            'repo_url': settings.REPO_URL,
            'django_version': django.get_version(),
            'user_agent': request.META['HTTP_USER_AGENT'],
            'library_count': query['title__count'],
            'library_size': query['filesize__sum'],
            'scrobbler_id': getattr(settings, 'SCROBBLER_USER', ''),
            'users': Player.objects.count() - 1,
        }
    )


def crash(_request):
    """Force an internal server error (for testing)"""
    raise Exception('crash forced')


@login_required
def js_object(request):
    """Exposes the TeamPlayer JavaScript namespace"""

    http_host = request.META.get('HTTP_HOST', 'localhost')
    http_host = http_host.partition(':')[0]
    return render(
        request,
        'teamplayer/teamplayer.js',
        {
            'websocket_url': get_websocket_url(request),
            'mpd_hostname': http_host,
            'mpd_http_port': settings.HTTP_PORT,
            'home': Station.main_station().pk,
            'username': request.player.username,
        },
        content_type='application/javascript'
    )


def player(request):
    """The audio player html"""
    station = request.station
    mpd_url = get_mpd_url(request, station)
    return render(request, 'teamplayer/player.html', {'mpd_url': mpd_url})


def redirect_to_home(request):
    main_station = Station.main_station()
    request.session['station_id'] = main_station.pk
    return redirect(reverse(home, args=(main_station.pk,)))

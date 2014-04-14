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
from django.shortcuts import get_object_or_404, redirect, render_to_response
from django.template import RequestContext
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response

from teamplayer import version_string
from teamplayer.conf import settings
from teamplayer.forms import (ChangeDJNameForm, CreateStationForm,
                              EditStationForm)
from teamplayer.lib import mktemp_file_from_request, songs, users
from teamplayer.lib.mpc import MPC
from teamplayer.lib.websocket import IPCHandler
from teamplayer.models import Entry, Player, Station
from teamplayer.serializers import (EntrySerializer, PlayerSerializer,
                                    StationSerializer)
from tp_library.models import SongFile

YEAR_IN_SECS = 365 * 24 * 60 * 60


class HttpResponseNoContent(HttpResponse):

    """HTTP 204 response"""
    status_code = 204


def get_mpd_url(request, station):
    http_host = request.META.get('HTTP_HOST', 'localhost')
    station = get_station_from_session(request)
    station_id = station.pk
    if ':' in http_host:
        http_host = http_host.split(':', 1)[0]
    return 'http://{0}:{1}/mpd.mp3'.format(http_host,
                                           settings.HTTP_PORT + station_id)


def get_websocket_url(request):
    http_host = request.META.get('HTTP_HOST', 'localhost')
    if ':' in http_host:
        http_host = http_host.split(':', 1)[0]
    return 'ws://{0}:{1}/'.format(http_host, settings.WEBSOCKET_PORT)


def get_station_from_session(request):
    main_station = Station.main_station()
    try:
        station_id = request.session['station_id']
    except KeyError:
        request.session['station_id'] = main_station.pk
        return main_station

    try:
        station = Station.objects.get(pk=station_id)
        return station
    except Station.DoesNotExist:
        request.session['station_id'] = main_station.pk
        return main_station


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

    return render_to_response(
        'teamplayer/home.html',
        {
            'mpd_url': get_mpd_url(request, station),
            'name': (request.user.player.dj_name
                     if request.user.player.dj_name
                     else 'Anonymous'),
            'show_player': True,
            'station': station,
            'station_id': station.pk,
            'home': Station.main_station().pk,
            'stations': Station.get_stations(),
            'user_owned_station': Station.from_user(request.user),
            'username': request.user.username,
        },
        context_instance=RequestContext(request)
    )


def register(request):
    return render_to_response(
        'teamplayer/home.html',
        {'register': True},
        context_instance=RequestContext(request)
    )


@api_view(['GET'])
@login_required
def show_queue(request):
    """
    View to display the titles in the user's queue.
    """
    station = get_station_from_session(request)

    entries = request.user.player.queue.entry_set.filter(station=station)
    seralizer = EntrySerializer(entries, many=True)
    return Response(seralizer.data)


@api_view(['GET', 'DELETE'])
@login_required
def show_entry(request, entry_id):
    """
    View to show an entry
    """
    entry = get_object_or_404(Entry,
                              pk=entry_id,
                              queue__player__user=request.user)
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
    """view to show user stats/settings"""
    players = Player.objects.all()
    serializer = PlayerSerializer(players, many=True)
    return Response(serializer.data)


@login_required
@require_POST
def add_to_queue(request):
    """
    Add song to the queue
    """
    station = get_station_from_session(request)

    if request.FILES:
        uploaded_file = next(request.FILES.values())
    else:
        uploaded_file = File(mktemp_file_from_request(request))

    try:
        entry = request.user.player.queue.add_song(uploaded_file, station)
    except songs.SongMetadataError:
        client_filename = request.FILES['files[]'].name
        if client_filename:
            extra = '%s: ' % client_filename
        else:
            extra = ''
        status = {'fail': ('%sThe song was not added because I did '
                           u'not recognize the type of file you sent' % extra)
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
    """Randomize the user's queue"""
    station = get_station_from_session(request)
    request.user.player.queue.randomize(station)
    return redirect(reverse('teamplayer.views.show_queue'))


@login_required
def order_by_rank(request):
    """Order your queue according to artist rank"""
    station = get_station_from_session(request)
    request.user.player.queue.order_by_rank(station)
    return redirect(reverse('teamplayer.views.show_queue'))


@login_required
@require_POST
def toggle_queue_status(request):
    """Toggle user's queue's active status"""
    new_status = bool(request.user.player.queue.toggle_status())
    IPCHandler.send_message(
        'queue_status',
        {
            'user': request.user.username,
            'status': new_status,
        }
    )
    return HttpResponse(
        json.dumps(new_status),
        content_type='application/json'
    )


@login_required
@require_POST
def toggle_auto_mode(request):
    """Toggle user's auto_mode flag"""
    request.user.player.toggle_auto_mode()
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
    station = get_station_from_session(request)

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
@transaction.commit_on_success
def reorder_queue(request):
    """
    Given comma-delimited string (of integers), re-order queue
    return the re-ordered list of ids in json format
    """
    ids = [x['id'] for x in request.user.player.queue.reorder(
        [int(i) for i in request.body.decode('utf-8').split(',')])
    ]

    return HttpResponse(
        json.dumps(ids),
        content_type='application/json'
    )


@login_required()
@require_POST
def change_dj_name(request):
    """Change user's "dj name" according to dj_name field"""
    form = ChangeDJNameForm(request.POST, user=request.user)

    if not form.is_valid():
        return HttpResponse(form.errors.values()[0])

    previous_dj_name = request.user.player.dj_name
    request.user.player.set_dj_name(form.cleaned_data['dj_name'])

    # send a notification the the spin doctor
    IPCHandler.send_message(
        message_type='dj_name_change',
        data={
            'user_id': request.user.pk,
            'previous_dj_name': previous_dj_name,
            'dj_name': form.cleaned_data['dj_name'],
        }
    )
    return HttpResponseNoContent('')


def logout(request):
    """Log out the user from TP"""
    auth_logout(request)
    messages.info(request, 'Thanks for playing.')
    return HttpResponseRedirect(reverse('django.contrib.auth.views.login'))


def registration(request):
    """The view that handles the actual registration form"""
    context = dict()
    context['form'] = UserCreationForm()
    context_instance = RequestContext(request)

    if request.method == "POST":
        context['form'] = form = UserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            try:
                Player.objects.get(user__username=username)
                context['error'] = 'User "%s" already exists.' % username
            except Player.DoesNotExist:
                user = users.create_user(username, password)
                IPCHandler.send_message(
                    'user_created', PlayerSerializer(user.player).data)
                messages.info(request, '%s registered. Please login.' %
                              username)
                return HttpResponse('<script>window.location="%s"</script>' %
                                    reverse('teamplayer.views.home'))

    context['users'] = Player.objects.all()
    return render_to_response('teamplayer/register.html', context,
                              context_instance)


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
        station = get_object_or_404(Station, creator=request.user)
    else:
        station = get_object_or_404(Station, pk=station_id)
    serializer = StationSerializer(station, context={'request': request})
    return Response(serializer.data)


def previous_station(request):
    """Redirect to the previous station"""
    station = get_station_from_session(request)
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
    station = get_station_from_session(request)
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
    message = u''
    form = EditStationForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data['name']
        station_id = form.cleaned_data['station_id']
        action = form.cleaned_data['action']

        station = get_object_or_404(Station,
                                    pk=station_id,
                                    creator=request.user)
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
        message = u'\n'.join([i[0] for i in form.errors.values()])

    return HttpResponse(message)


@login_required
@require_POST
def create_station(request):
    form = CreateStationForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data['name']

        station = Station.create_station(name, request.user)
        IPCHandler.send_message('station_create', station.pk)
        return HttpResponseNoContent()
    return HttpResponse('Error creating station', content_type='text/plain')


def about(request):
    """about/copyright page"""

    query = SongFile.objects.aggregate(
        Count('title'),
        Sum('filesize')
    )

    return render_to_response(
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
        },
        context_instance=RequestContext(request)
    )


def crash(_request):
    """Force an internal server error (for testing)"""
    raise Exception('crash forced')


def js_object(request):
    """Exposes the TeamPlayer JavaScript namespace"""

    http_host = request.META.get('HTTP_HOST', 'localhost')
    if ':' in http_host:
        http_host = http_host.split(':', 1)[0]
    return render_to_response(
        'teamplayer/teamplayer.js',
        {
            'websocket_url': get_websocket_url(request),
            'mpd_hostname': http_host,
            'mpd_http_port': settings.HTTP_PORT,
            'home': Station.main_station().pk,
            'username': request.user.username,
        },
        context_instance=RequestContext(request),
        content_type='application/javascript'
    )


def player(request):
    """The audio player html"""
    station = get_station_from_session(request)
    return render_to_response(
        'teamplayer/player.html',
        {
            'mpd_url': get_mpd_url(request, station),
        }
    )


def redirect_to_home(request):
    main_station = Station.main_station()

    request.session['station_id'] = main_station.pk
    return redirect(reverse(home, args=(main_station.pk,)))

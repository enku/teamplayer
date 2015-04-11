"""
Library to deal with song files and song metadata
"""
import contextlib
import datetime
import socket
import time
from functools import lru_cache
from http.client import HTTPException
from urllib.error import URLError

import pylast
from django.conf import settings as django_settings
from django.db.models import Count
from mutagen import File

from teamplayer import logger, models, scrobbler
from teamplayer.conf import settings
from teamplayer.lib import first_or_none, list_iter, now, remove_pedantic

CLEAR_IMAGE_URL = django_settings.STATIC_URL + 'images/clear.png'
MIME_MAP = {
    'audio/ape': 'ape',
    'audio/flac': 'flac',
    'audio/mp3': 'mp3',
    'audio/mp4': 'mp4',
    'audio/mpeg': 'mp3',
    'audio/ogg': 'ogg',
    'audio/vorbis': 'ogg',
    'audio/x-flac': 'flac',
}
LASTFM_APIKEY = settings.LASTFM_APIKEY


@contextlib.contextmanager
def sockettimeout(secs):
    """Context manager to temporarily set the default socket timeout"""
    orig_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(secs)
    yield
    socket.setdefaulttimeout(orig_timeout)


class SongMetadataError(Exception):

    """When song metadata could not be parsed"""
    pass


def get_song_metadata(filename):
    """Return a dict of song metadata for filename

    Given the filename, return a dict of metadata consisting of:

        * artist: the song artist
        * title: the song title
        * type: the song's type
        * mimetype: the song's mimetype

    Raise SongMetaDataError if this cannot be determined.
    """
    try:
        mutagen_data = File(filename, easy=True)
        artist = first_or_none(mutagen_data, 'artist') or 'Unknown'
        title = first_or_none(mutagen_data, 'title') or 'Unknown'
        mimetype = mutagen_data.mime[0]
        filetype = MIME_MAP[mimetype]

        return {
            'artist': artist,
            'title': title,
            'type': filetype,
            'mimetype': mimetype
        }

    except Exception as error:
        raise SongMetadataError(str(error))


def time_to_secs(time_str):
    """
    Where time_str is a string of the format mm:ss or hh:mm:ss, return
    int number of seconds
    """

    parts = time_str.split(':')
    if len(parts) == 2:
        parts = ['0'] + parts
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])

    return 3600 * hours + 60 * minutes + seconds


@lru_cache(maxsize=256)
def get_image_url_for(artist):
    """Return a URL for image of artist"""
    if not artist:
        return CLEAR_IMAGE_URL

    network = pylast.LastFMNetwork(api_key=LASTFM_APIKEY)
    lfm_artist = network.get_artist(artist)

    try:
        return lfm_artist.get_cover_image()
    except pylast.WSError:
        return CLEAR_IMAGE_URL


@lru_cache(maxsize=512)
def get_similar_artists(artist):
    """
    Generator for finding similar artists to *artist*.  Uses the last.fm
    api to fetch the list
    """
    network = pylast.LastFMNetwork(api_key=LASTFM_APIKEY)
    lfm_artist = network.get_artist(artist)
    lfm_similar = lfm_artist.get_similar()
    similar = []

    for item in lfm_similar:
        similar.append(item.item.name)

    return similar


def best_song_from_player(player, station, previous_artist=None):
    """
    Given the player and station, get the best song from the player's queue,
    taking into account the player's auto_mode and previous_artist.

    If no relevant song is found, return None.
    """
    queue = player.queue

    if not queue.active:
        return None

    if player.auto_mode:
        entry = auto_find_song(previous_artist, queue, station)
        if entry:
            return entry

    entries = queue.entry_set.filter(station=station)
    if entries:
        return entries[0]

    return None


def find_a_song(players, station, previous_player=None, previous_artist=None):
    """
    Rotate through the players list until you find a song.  If no one has a
    song in their station/queue after one loop then return None

    If previous_artist is defined, and player.auto_mode is True, try to find a
    song in the player's queue whose artist is similar to the current mood
    without repeating the previous_artist.
    """
    wants_dj_ango = (settings.SHAKE_THINGS_UP
                     and station == models.Station.main_station())
    if wants_dj_ango:
        dj_ango = models.Player.dj_ango()
        dj_ango.queue.auto_fill(
            settings.SHAKE_THINGS_UP,
            station=station,
            qs_filter=settings.SHAKE_THINGS_UP_FILTER,
            minimum=1,
        )

    for player in list_iter(players, previous_player):
        entry = best_song_from_player(player, station, previous_artist)
        if entry:
            return entry

    if wants_dj_ango:
        return auto_find_song(previous_artist, dj_ango.queue, station)
    return None


def auto_find_song(previous_artist, queue, station):
    """
    Return first song from an artist that is similar to the current mood,
    but not repeating *previous_artist*.  If no similar artist/song can
    be found, return the first entry in *queue*. If *queue* is empty,
    return None
    """
    entries = (queue.entry_set.filter(station=station)
               .exclude(artist__iexact=previous_artist))

    if entries.count() == 0:
        return None

    artists = set([i.artist.lower() for i in entries])
    if len(artists) == 1:
        # the similarity is inconsequential
        return entries[0]

    one_day = now() - datetime.timedelta(hours=24)
    mood_artists = (models.Mood.objects
                    .filter(timestamp__gt=one_day, station=station)
                    .exclude(artist__iexact=previous_artist)
                    .values('artist')
                    .order_by()
                    .annotate(Count('artist'))
                    .order_by('-artist__count'))
    for mood_artist in mood_artists:
        a = mood_artist['artist'].lower()
        if a in artists:
            logger.info('“%s” fits the mood', mood_artist['artist'])
            return entries.filter(artist__iexact=a)[0]

    return entries[0]


def scrobble_song(song, now_playing=False):
    """
    scrobble this song.

    Return True if the song was successfully scrobbled, else return False.
    """
    logger.debug('Scrobbling “%s” by %s', song['title'], song['artist'])
    if not scrobbler.POST_URL:
        # we are not logged in
        try:
            scrobbler.login(settings.SCROBBLER_USER,
                            settings.SCROBBLER_PASSWORD)
        except (URLError, HTTPException, scrobbler.ProtocolError):
            return False

    artist = song['artist']
    title = song['title']
    length = song['total_time']
    start_time = int(time.mktime(time.localtime())) - length  # not exact..
    try:
        if now_playing:
            scrobbler.now_playing(artist, title, length=length)
        else:
            scrobbler.submit(artist, title, start_time, length=length,
                             autoflush=True)
    except (URLError, HTTPException, scrobbler.ProtocolError):
        logger.error('Error scrobbing song: %s', song, exc_info=True)
        return False
    except (scrobbler.SessionError, scrobbler.BackendError, OSError):
        # usually this means our session timed out, just log in again
        try:
            scrobbler.login(settings.SCROBBLER_USER,
                            settings.SCROBBLER_PASSWORD)
        except scrobbler.ProtocolError as error:
            # We've probably logged on too many times, neglect this one
            logger.error('Error scrobbing song: %s: %s', song, error)
            return False
        if now_playing:
            scrobbler.now_playing(artist, title, length=length)
        else:
            scrobbler.submit(artist, title, start_time, length=length,
                             autoflush=True)
    return True

remove_pedantic()

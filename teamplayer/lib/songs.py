"""
Library to deal with song files and song metadata
"""
import contextlib
import datetime
import logging
import socket
import time
import urllib.parse
from functools import lru_cache
from http.client import HTTPException
from urllib.error import URLError
from urllib.request import urlopen
from xml.etree import ElementTree

from django.conf import settings as django_settings
from django.db.models import Count
from mutagen import File

from teamplayer import models, scrobbler
from teamplayer.conf import settings
from teamplayer.lib import first_or_none, list_iter, now, remove_pedantic

LOGGER = logging.getLogger('teamplayer.songlib')
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


def url_friendly_artist(artist):
    """
    Return *artist* in such a way that it is acceptable by the
    last.fm api when used in …/artist/*artist*/similar.txt for example.

    Currently this is used to get the similar artist url.  Might
    it also be useful for other things last.fm?
    """
    new_artist = artist

    if type(new_artist) is str:
        new_artist = artist.encode('utf-8', 'ignore')

    new_artist = artist.replace('.', '')
    new_artist = new_artist.replace('/', '')
    new_artist = urllib.parse.quote(new_artist)
    return new_artist


@lru_cache(maxsize=256)
def get_image_url_for(artist):
    """Return a URL for image of artist"""
    if not artist:
        return CLEAR_IMAGE_URL

    encoded_artist = url_friendly_artist(artist)
    tmpl = ('http://ws.audioscrobbler.com/2.0/?method=artist.getInfo'
            '&artist={0}&api_key={1}&limit=1')
    api_url = tmpl.format(encoded_artist, LASTFM_APIKEY)

    with sockettimeout(3.0):
        try:
            response = urllib.request.urlopen(api_url)
        except IOError:
            return CLEAR_IMAGE_URL

    try:
        root = ElementTree.parse(response)
    except:
        # FIXME: This needs to be fixed, but different versions of Python
        # raise different exceptions, so we use a catch-all for now
        LOGGER.error('Error parsing response from %s', api_url)
        return CLEAR_IMAGE_URL
    images = root.findall('./artist/image')
    for image in images:
        if image.get('size') == 'extralarge':
            image_url = image.text
            break
    image_url = image_url or CLEAR_IMAGE_URL
    return image_url


@lru_cache(maxsize=512)
def get_similar_artists(artist):
    """
    Generator for finding similar artists to *artist*.  Uses the last.fm
    api to fetch the list
    """
    encoded_artist = url_friendly_artist(artist)
    url = ('http://ws.audioscrobbler.com/2.0/artist/%s/similar.txt' %
           encoded_artist)
    try:
        data = urlopen(url).read().decode('utf-8')
    except (URLError, HTTPException):
        LOGGER.error('URLError: %s', url, exc_info=True)
        return []

    similar = set()
    for line in data.split('\n'):
        try:
            similar_artist = line.strip().split(',')[-1]
        except IndexError:
            continue
        # damned entity references
        similar_artist = similar_artist.replace("&amp;", "&")
        similar.add(similar_artist)
    return similar


def best_song_from_player(player, station, previous_artist=None):
    """
    Given the player and station, get the best song from the player's queue,
    taking into account the player's auto_mode and previous_artist.

    If no relevant song is found, return None.
    """
    try:
        queue = player.queue
    except models.Player.DoesNotExist:
        return None

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
        return auto_find_song(
            previous_artist,
            dj_ango.queue,
            station
        )
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
            LOGGER.info(u'“%s” fits the mood', mood_artist['artist'])
            return entries.filter(artist__iexact=a)[0]

    return entries[0]


def scrobble_song(song, now_playing=False):
    """
    scrobble this song.

    Return True if the song was successfully scrobbled, else return False.
    """
    if not scrobbler.POST_URL:
        # we are not logged in
        try:
            scrobbler.login(settings.SCROBBLER_USER,
                            settings.SCROBBLER_PASSWORD)
        except (URLError, HTTPException, scrobbler.ProtocolError):
            return False

    # song => (u'DJ', 'Purity Ring', 'Ungirthed', 169, 19, 0)
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
        LOGGER.error('Error scrobbing song: %s', song, exc_info=True)
        return False
    except (scrobbler.SessionError, scrobbler.BackendError):
        # usually this means our session timed out, just log in again
        try:
            scrobbler.login(settings.SCROBBLER_USER,
                            settings.SCROBBLER_PASSWORD)
        except scrobbler.ProtocolError as error:
            # We've probably logged on too many times, neglect this one
            LOGGER.error('Error scrobbing song: %s: %s', song, error)
            return False
        if now_playing:
            scrobbler.now_playing(artist, title, length=length)
        else:
            scrobbler.submit(artist, title, start_time, length=length,
                             autoflush=True)
    return True

remove_pedantic()

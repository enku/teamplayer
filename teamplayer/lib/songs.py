# -*- coding: utf-8 -*-
"""
Library to deal with song files and song metadata
"""
import contextlib
import datetime
from httplib import HTTPException
import logging
import socket
import time
import urllib
import urllib2
from xml.etree import ElementTree

from django.db.models import Count
from django.conf import settings as django_settings
from django.contrib.auth.models import User

from mutagen import File

from teamplayer import models
from teamplayer import scrobbler
from teamplayer.conf import settings
from teamplayer.lib import list_iter, now, first_or_none, remove_pedantic

LOGGER = logging.getLogger('teamplayer.songlib')
CLEAR_IMAGE_URL = django_settings.STATIC_URL + 'images/clear.png'
ARTIST_IMAGE_CACHE = {
    '': CLEAR_IMAGE_URL,
    None: CLEAR_IMAGE_URL
}
SIMILAR_ARTIST_CACHE = dict()
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
    """Given filename, return (artist, title, type)"""

    try:
        metadata = File(filename, easy=True)
        artist = first_or_none(metadata, 'artist') or 'Unknown'
        title = first_or_none(metadata, 'title') or 'Unknown'
        mimetype = metadata.mime[0]
        filetype = MIME_MAP[mimetype]

        return (artist, title, filetype)

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
    Return «artist» in such a way that it is acceptable by the
    last.fm api when used in …/artist/«artist»/similar.txt for example.

    Currently this is used to get the similar artist url.  Might
    it also be useful for other things last.fm?
    """
    new_artist = artist

    if type(new_artist) is unicode:
        new_artist = artist.encode('utf-8', 'ignore')

    new_artist = artist.replace('.', '')
    new_artist = new_artist.replace('/', '')
    new_artist = urllib.quote(new_artist)
    return new_artist


def get_image_url_for(artist):
    """Return a URL for image of artist"""
    image_url = ARTIST_IMAGE_CACHE.get(artist, None)
    if image_url:
        LOGGER.debug('Artist image cache hit for %s' % artist)
        return image_url

    encoded_artist = url_friendly_artist(artist)
    tmpl = ('http://ws.audioscrobbler.com/2.0/?method=artist.getInfo'
            '&artist={0}&api_key={1}&limit=1')
    api_url = tmpl.format(encoded_artist, LASTFM_APIKEY)

    with sockettimeout(3.0):
        try:
            response = urllib.urlopen(api_url)
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
    ARTIST_IMAGE_CACHE[artist] = image_url
    return image_url


def get_similar_artists(artist):
    """
    Generator for finding similar artists to «artist».  Uses the last.fm
    api to fetch the list
    """
    data = SIMILAR_ARTIST_CACHE.get(artist, None)
    if data is None:
        encoded_artist = url_friendly_artist(artist)
        url = ('http://ws.audioscrobbler.com/2.0/artist/%s/similar.txt' %
               encoded_artist)
        SIMILAR_ARTIST_CACHE[artist] = list()
        try:
            data = urllib2.urlopen(url)
        except (urllib2.URLError, HTTPException):
            LOGGER.error('URLError: %s', url, exc_info=True)
            return
        for line in data:
            try:
                similar_artist = line.strip().split(',')[2]
            except IndexError:
                continue
            # damned entity references
            similar_artist = similar_artist.replace("&amp;", "&")
            SIMILAR_ARTIST_CACHE[artist].append(similar_artist)
            yield similar_artist
    else:
        for similar_artist in data:
            yield similar_artist


def log_mood(artist, station):
    """Log the artist and similar artists in the Mood database"""
    models.Mood.objects.create(
        artist=artist,
        station=station
    )

    similar_artists = get_similar_artists(artist)
    for artist in similar_artists:
        models.Mood.objects.create(
            artist=artist,
            station=station,
        )


def best_song_from_user(user, station, previous_artist=None):
    """
    Given the user and station, get the best song from the user's queue,
    taking into account the user's auto_mode and previous_artist.

    If no relevant song is found, return None.
    """
    try:
        queue = user.userprofile.queue
    except models.UserProfile.DoesNotExist:
        return None

    if not queue.active:
        return None

    if user.userprofile.auto_mode:
        entry = auto_find_song(previous_artist, queue, station)
        if entry:
            return entry

    entries = queue.entry_set.filter(station=station)
    if entries:
        return entries[0]

    return None


def find_a_song(users, station, previous_user=None, previous_artist=None):
    """
    Rotate through the user list until you find a song.  If no one
    has a song in their station/queue after one loop then return None

    If previous_artist is defined, and user.userprofile.auto_mode is True,
    try to find a song in the user's queue whose artist is similar to
    the current mood without repeating the previous_artist.
    """
    wants_dj_ango = (settings.SHAKE_THINGS_UP
                     and station == models.Station.main_station())
    if wants_dj_ango:
        dj_ango = User.dj_ango()
        dj_ango.userprofile.queue.auto_fill(
            settings.SHAKE_THINGS_UP,
            station=station,
            qs_filter=settings.SHAKE_THINGS_UP_FILTER,
            minimum=1,
        )

    for user in list_iter(users, previous_user):
        entry = best_song_from_user(user, station, previous_artist)
        if entry:
            return entry

    if wants_dj_ango:
        return auto_find_song(
            previous_artist,
            dj_ango.userprofile.queue,
            station
        )
    return None


def auto_find_song(previous_artist, queue, station):
    """
    Return first song from an artist that is similar to the current mood,
    but not repeating «previous_artist».  If no similar artist/song can
    be found, return the first entry in «queue». If «queue» is empty,
    return None
    """
    entries = queue.entry_set.filter(station=station)
    if entries.count() == 0:
        return None

    artists = set([i.artist.lower() for i in entries])
    if len(artists) == 1:
        # the similarity is inconsequential
        return entries[0]

    one_day = now() - datetime.timedelta(hours=24)
    mood_artists = (models.Mood.objects
                    .filter(timestamp__gt=one_day, station=station)
                    .values('artist')
                    .order_by()
                    .annotate(Count('artist'))
                    .order_by('-artist__count'))
    for mood_artist in mood_artists:
        a = mood_artist['artist'].lower()
        if a in artists:
            LOGGER.info(u'“%s” fits the mood', mood_artist['artist'])
            return entries.filter(artist__iexact=a)[0]

    return None


def scrobble_song(song, now_playing=False):
    """
    scrobble this song.

    Return True if the song was successfully scrobbled, else return False.
    """
    if not scrobbler.POST_URL:
        # we are not logged in
        scrobbler.login(settings.SCROBBLER_USER,
                        settings.SCROBBLER_PASSWORD)

    # song => (u'DJ', 'Purity Ring', 'Ungirthed', 169, 19, 0)
    artist = unicode(song['artist'], 'utf-8', 'replace')
    title = unicode(song['title'], 'utf-8', 'replace')
    length = song['total_time']
    start_time = int(time.mktime(time.localtime())) - length  # not exact..
    try:
        if now_playing:
            scrobbler.now_playing(artist, title, length=length)
        else:
            scrobbler.submit(artist, title, start_time, length=length,
                             autoflush=True)
    except (urllib2.URLError, HTTPException, scrobbler.ProtocolError):
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

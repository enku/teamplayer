"""
Library to deal with song files and song metadata
"""
import datetime
import random
from functools import lru_cache

import pylast
from django.conf import settings as django_settings
from django.db.models import Count
from mutagen import File

from teamplayer import logger, models
from teamplayer.conf import settings
from teamplayer.lib import first_or_none, list_iter, now, spotify

CLEAR_IMAGE_URL = django_settings.STATIC_URL + "images/clear.png"
MIME_MAP = {
    "audio/ape": "ape",
    "audio/flac": "flac",
    "audio/mp1": "mp3",
    "audio/mp2": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/vorbis": "ogg",
    "audio/x-flac": "flac",
}
LASTFM_APIKEY = settings.LASTFM_APIKEY


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
        artist = first_or_none(mutagen_data, "artist") or "Unknown"
        title = first_or_none(mutagen_data, "title") or "Unknown"
        album = first_or_none(mutagen_data, "album")
        mimetype = mutagen_data.mime[0]
        filetype = MIME_MAP[mimetype]

        return {
            "artist": artist,
            "title": title,
            "album": album,
            "type": filetype,
            "mimetype": mimetype,
        }

    except Exception as error:
        raise SongMetadataError(str(error))


def time_to_secs(time_str):
    """
    Where time_str is a string of the format mm:ss or hh:mm:ss, return
    int number of seconds
    """

    parts = time_str.split(":")
    if len(parts) == 2:
        parts = ["0"] + parts
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])

    return 3600 * hours + 60 * minutes + seconds


@lru_cache(maxsize=256)
def get_image_url_for(artist: str) -> str:
    """Return a URL for image of artist"""
    if not artist:
        return CLEAR_IMAGE_URL

    cover_image = None

    # data = {['artists']['items'][]['images'][]['url']}
    try:
        data = spotify.search("artist", artist)
    except:
        logger.exception("Error searching artist in Spotify: %s", artist)
    else:
        items = data["artists"]["items"]
        if items:
            images = items[0]["images"]
            if images:
                cover_image = random.choice(images)["url"]

    return cover_image or CLEAR_IMAGE_URL


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


@lru_cache(maxsize=256)
def top_artists_from_tag(tag, limit=100):
    """Return a list of artists from the given "tag"

    Args:
        tag (str): lowercase (Lastfm tag)
        limit (int): maximal number of tags to return (default: 100)

    Returns: A list of tag strings
    """
    network = pylast.LastFMNetwork(api_key=LASTFM_APIKEY)
    pylast_tag = pylast.Tag(tag, network)

    try:
        top_artists = pylast_tag.get_top_artists(limit=limit)
    except pylast.WSError as error:
        if int(error.status) == 6:
            # invalid params (i.e. no such tag)
            return []
        raise

    return [x.item.name for x in top_artists]


def artists_from_tags(tags):
    tag_sets = []

    for tag in tags:
        tag_artists = top_artists_from_tag(tag)
        tag_sets.append(set(tag_artists))

    artists = tag_sets[0]
    for tag_set in tag_sets[1:]:
        artists.intersection_update(tag_set)

    return list(artists)


def split_tag_into_words(tag):
    """Return `tag` split into words.

    The best way to to describe this is to show examples:

        "loveSongs" -> "love songs"

        "LoveSongs" -> "love songs"

        "lovesongs" -> "lovesongs"

        "LOVESONGS" -> "lovesongs"

        "love_songs" -> "love songs"
    """
    words = [""]
    word = 0

    for char in tag:
        if words[word] == "":
            words[word] = char

        elif char == "_":
            words.append("")
            word = word + 1
            prevchar = char
            continue

        elif char.isupper() and prevchar.islower():
            words.append(char)
            word = word + 1

        else:
            words[word] = words[word] + char
        prevchar = char

    return " ".join(words).lower().strip()


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
    wants_dj_ango = settings.SHAKE_THINGS_UP
    station = models.Station.objects.get(pk=station.pk)  # reload

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
    entries = queue.entry_set.filter(station=station).exclude(
        artist__iexact=previous_artist
    )

    if entries.count() == 0:
        return None

    artists = set([i.artist.lower() for i in entries])
    if len(artists) == 1:
        # the similarity is inconsequential
        return entries[0]

    one_day = now() - datetime.timedelta(hours=24)
    mood_artists = (
        models.Mood.objects.filter(timestamp__gt=one_day, station=station)
        .exclude(artist__iexact=previous_artist)
        .values("artist")
        .order_by()
        .annotate(Count("artist"))
        .order_by("-artist__count")
    )
    for mood_artist in mood_artists:
        a = mood_artist["artist"].lower()
        if a in artists:
            logger.info("“%s” fits the mood", mood_artist["artist"])
            return entries.filter(artist__iexact=a)[0]

    return entries[0]


def scrobble_song(song, now_playing=False):
    """
    scrobble this song.

    Return True if the song was successfully scrobbled, else return False.
    """
    password_hash = pylast.md5(settings.SCROBBLER_PASSWORD)
    network = pylast.LastFMNetwork(
        api_key=LASTFM_APIKEY,
        api_secret=settings.LASTFM_APISECRET,
        username=settings.SCROBBLER_USER,
        password_hash=password_hash,
    )

    artist = song["artist"]
    title = song["title"]
    album = song["album"]
    length = song["total_time"]

    try:
        logger.debug("Scrobbling “%s” by %s", song["title"], song["artist"])
        if now_playing:
            network.update_now_playing(
                artist,
                title,
                album=album,
                duration=length,
            )
        else:
            timestamp = int(now().timestamp()) - length
            network.scrobble(
                artist,
                title,
                timestamp,
                album=album,
                duration=length,
            )
    except pylast.WSError:
        return False

    return True

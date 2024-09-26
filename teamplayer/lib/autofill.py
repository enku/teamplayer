"""TeamPlayer Auto-Fill strategies

Each strategy shall be a function with the following kwargs::

    def autofill_strategy(*, queryset, entries_needed, station):
        ...

        return list_of_songs

It should return a list of ``teamplayer.models.Song`` objects that are
a subset of *queryset* and whose length is equal to *entries_needed* or
smaller of the strategy was not able to gather enough songs.  The *station*
argument is the ``Station`` for which the songs are being considered.
"""

import datetime
import random

from django.db.models import Count, QuerySet
from django.utils import timezone

from teamplayer import logger
from teamplayer.conf import settings
from teamplayer.models import LibraryItem, Mood, Station

from .songs import artists_from_tags, split_tag_into_words


def auto_fill_random(
    *,
    queryset: QuerySet[LibraryItem],
    entries_needed: int,
    station: Station,  # pylint: disable=unused-argument
) -> list[LibraryItem]:
    """Return at most *entries_needed* LibraryItems from the *queryset*.

    The songs are randomly scattered among the *queryset*
    """
    song_files: set[LibraryItem] = set()
    song_count = queryset.count()

    if not song_count:
        return []

    num_to_get = min(song_count, entries_needed)

    while len(song_files) < num_to_get:
        song_file = queryset[random.randint(0, song_count - 1)]
        song_files.add(song_file)

    return list(song_files)


def auto_fill_contiguous(
    *,
    queryset: QuerySet[LibraryItem],
    entries_needed: int,
    station: Station,  # pylint: disable=unused-argument
) -> list[LibraryItem]:
    """Return at most *entries_needed* LibraryItems from the *queryset*.

    The songs are selected randomly but are contiguous among the *queryset*
    """
    song_count = queryset.count()

    if not song_count:
        return []

    min_first_song = max(0, song_count - entries_needed)
    first_song_idx = random.randint(0, min_first_song)
    song_files = queryset[first_song_idx : first_song_idx + entries_needed]

    return list(song_files)


def auto_fill_mood(
    *,
    queryset: QuerySet[LibraryItem],
    entries_needed: int,
    station: Station,
    seconds: int | None = None,
) -> list[LibraryItem]:
    """Return at most *entries_needed* LibraryItems from the *queryset*.

    The songs are selected depending on the current "mood".
    """
    num_top_artists = settings.AUTOFILL_MOOD_TOP_ARTISTS
    seconds = seconds or settings.AUTOFILL_MOOD_HISTORY
    history = timezone.now() - datetime.timedelta(seconds=seconds)
    query = (
        Mood.objects.filter(timestamp__gte=history, station=station)
        .exclude(artist="")
        .values("artist")
        .annotate(Count("id"))
        .order_by("-id__count")[:num_top_artists]
    )

    top_artists = [i["artist"] for i in query]
    random.shuffle(top_artists)

    liked_songs = []
    for artist in top_artists:
        song = queryset.filter(artist__iexact=artist)
        if not song.exists():
            continue
        index = random.randint(1, song.count()) - 1
        liked_songs.append(song[index])

        if len(liked_songs) == entries_needed:
            break

    additional = []
    still_needed = entries_needed - len(liked_songs)
    if still_needed > 0:
        qs = queryset.exclude(pk__in=[i.pk for i in liked_songs])
        # keep going back in history up to 24 hours to find artists that fit
        # the mood
        if seconds < 86400:
            seconds = seconds + settings.AUTOFILL_MOOD_HISTORY
            additional = auto_fill_mood(
                queryset=qs,
                entries_needed=still_needed,
                station=station,
                seconds=seconds,
            )
        else:
            additional = auto_fill_random(
                entries_needed=still_needed,
                queryset=qs,
                station=station,
            )

    songs = liked_songs + additional
    random.shuffle(songs)

    return songs


def auto_fill_from_tags(
    *, queryset: QuerySet[LibraryItem], entries_needed: int, station: Station
) -> list[LibraryItem]:
    """Return at most `entries_needed` LibraryItems with `station`'s tags

    Gets the tags from the `station.name`, gets artists with those tags and
    then returns random songs from `queryset` that have artists with those
    tags.
    """
    stationname = station.name
    tags = stationname.split()
    tags = [split_tag_into_words(i[1:]) for i in tags if i.startswith("#")]
    logger.debug("Tags: %s", ", ".join(tags))
    artists = artists_from_tags(tags)
    songfiles = queryset.filter(artist__in=artists)

    count = songfiles.count()
    if count > entries_needed:
        indices = random.sample(range(count), entries_needed)
        songs = [songfiles[i] for i in indices]
    else:
        songs = list(songfiles)

    random.shuffle(songs)

    return songs

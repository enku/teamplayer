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
import random


def auto_fill_random(*, queryset, entries_needed, station):
    """Return at most *entries_needed* SongFiles from the *queryset*.

    The songs are randomly scattered among the *queryset*
    """
    song_files = set()
    song_count = queryset.count()

    if not song_count:
        return []

    num_to_get = min(song_count, entries_needed)

    while len(song_files) < num_to_get:
        song_file = queryset[random.randint(0, song_count - 1)]
        song_files.add(song_file)

    return list(song_files)


def auto_fill_contiguous(*, queryset, entries_needed, station):
    """Return at most *entries_needed* SongFiles from the *queryset*.

    The songs are selected randomly but are contiguous among the *queryset*
    """
    song_count = queryset.count()

    if not song_count:
        return []

    min_first_song = max(0, song_count - entries_needed)
    first_song_idx = random.randint(0, min_first_song)
    song_files = queryset[first_song_idx:first_song_idx + entries_needed]

    return list(song_files)

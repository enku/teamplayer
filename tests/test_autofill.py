"""Tests for the autofill strategies"""

import datetime
import pickle
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.utils import timezone
from unittest_fixtures import Fixtures, fixture, given

from teamplayer.lib import songs as songslib
from teamplayer.lib.autofill import (
    auto_fill_contiguous,
    auto_fill_from_tags,
    auto_fill_mood,
    auto_fill_random,
)
from teamplayer.models import LibraryItem, Mood, Player, Station

from . import utils

ARTISTS = [
    "Britney Spears",
    "KMFDM",
    "Kanye West",
    "Katie Melua",
    "Marilyn Manson",
    "Nine Inch Nails",
    "Norah Jones",
    "Sufjan Stevens",
    "The Glitch Mob",
    "edIT",
]


@fixture()
def songs_fixture(_: Fixtures) -> list[LibraryItem]:
    songs: list[LibraryItem] = []
    dj_ango = Player.dj_ango()

    # let's fill the library with some songage
    for artist in ARTISTS:
        filename = f'{artist.lower().replace(" ", "_")}.mp3'
        songfile = LibraryItem(
            filename=filename,
            artist=artist,
            title="Silent Night",
            album="Various Artists Do Silent Night",
            genre="Unknown",
            length=300,
            filesize=3000,
            station_id=1,
            mimetype="audio/mp3",
            added_by=dj_ango,
        )
        songfile.save()
        songs.append(songfile)
    return songs


@given(songs_fixture)
class RandomTest(TestCase):
    """tests for the random autofill strategy"""

    def test_empty_queryset_returns_empty_list(self, fixtures: Fixtures) -> None:
        # given the empty queryset
        queryset = LibraryItem.objects.none()

        # when we call the random strategy
        result = auto_fill_random(
            entries_needed=10, queryset=queryset, station=Station.main_station()
        )

        # then it returns an empty list
        self.assertEqual(result, [])

    def test_queryset_less_than_needed_returns_entire_queryset(
        self, fixtures: Fixtures
    ) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()[:5]

        # given the number of entries needed
        entries_needed = 30

        # when we call the random strategy
        result = auto_fill_random(
            entries_needed=entries_needed,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then it returns the entire queryset
        all_songs = set(queryset)
        returned_songs = set(result)
        self.assertEqual(returned_songs, all_songs)

    def test_queryset_more_than_needed_returns_only_needed(
        self, fixtures: Fixtures
    ) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()

        # given the number of entries needed
        entries_needed = 5

        # when we call the random strategy
        result = auto_fill_random(
            entries_needed=entries_needed,
            queryset=queryset,
            station=Station.main_station(),
        )

        # then it only returns the number needed
        self.assertTrue(len(result), 5)

        # and they're all unique
        ids = set(song.pk for song in result)
        self.assertEqual(len(ids), 5)


@given(songs_fixture)
class ContiguousTest(TestCase):
    """tests for the contiguous autofill strategy"""

    def test_empty_queryset_returns_empty_list(self, fixtures: Fixtures) -> None:
        # given the empty queryset
        queryset = LibraryItem.objects.none()

        # when we call the contiguous strategy
        result = auto_fill_contiguous(
            entries_needed=10, queryset=queryset, station=Station.main_station()
        )

        # then it returns an empty list
        self.assertEqual(result, [])

    def test_returns_songs_in_queryset_order(self, fixtures: Fixtures) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()

        # when we call the contiguous strategy
        result = auto_fill_contiguous(
            entries_needed=4, queryset=queryset, station=Station.main_station()
        )

        # then the songs returned are in the same order as they are in the
        # queryset
        queryset_list = list(queryset)
        index = queryset_list.index(result[0])
        ordered_songs = queryset_list[index : index + 4]
        self.assertEqual(result, ordered_songs)

    def test_entries_needed_less_than_queryset_returns_full_set_ordered(
        self, fixtures: Fixtures
    ) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()[:5]

        # when we call the contiguous strategy needing more songs than are in
        # the queryset
        result = auto_fill_contiguous(
            entries_needed=20, queryset=queryset, station=Station.main_station()
        )

        # then we get back a list containing the entire queryset in order
        queryset_list = list(queryset)
        self.assertEqual(result, queryset_list)


@given(songs_fixture)
class MoodTest(TestCase):
    """tests for the mood strategy"""

    def setUp(self):
        super().setUp()

        station = Station.main_station()

        # let's set the mood ;-)
        path = "teamplayer.models.lib.songs.get_similar_artists"
        patcher = patch(path)
        get_similar_artists = patcher.start()
        get_similar_artists.return_value = ["Marilyn Manson", "KMFDM"]
        Mood.log_mood("Nine Inch Nails", station)
        Mood.log_mood("Nine Inch Nails", station)
        Mood.log_mood("Nine Inch Nails", station)
        get_similar_artists.return_value = ["KMFDM"]  # I know, nothing like NJ
        Mood.log_mood("Norah Jones", station)
        # make the last one kinda old
        norah_jones_mood = Mood.objects.get(artist="Norah Jones")
        two_hours_ago = timezone.now() - datetime.timedelta(hours=120)
        norah_jones_mood.timestamp = two_hours_ago
        norah_jones_mood.save()

        self.addCleanup(patcher.stop)

    def test_finds_top_artists(self, fixtures: Fixtures) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()

        # when we call the mood strategy with 1 entry needed
        station = Station.main_station()
        with patch("teamplayer.lib.autofill.settings") as settings:
            settings.AUTOFILL_MOOD_TOP_ARTISTS = 1
            settings.AUTOFILL_MOOD_HISTORY = 86400
            result = auto_fill_mood(
                entries_needed=1, queryset=queryset, station=station
            )

        # then it gives us the one song by the top artist
        self.assertEqual(len(result), 1)
        song = result[0]
        self.assertEqual(song.artist, "KMFDM")

    def test_finds_top_artists2(self, fixtures: Fixtures) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()

        # when we call the mood strategy with 3 entries needed
        station = Station.main_station()
        with patch("teamplayer.lib.autofill.settings") as settings:
            settings.AUTOFILL_MOOD_TOP_ARTISTS = 3
            settings.AUTOFILL_MOOD_HISTORY = 86400
            result = auto_fill_mood(
                entries_needed=3, queryset=queryset, station=station
            )

        # then it gives us the songs by the top 3 artists
        self.assertEqual(len(result), 3)
        artists = set(i.artist for i in result)
        self.assertEqual(artists, {"Nine Inch Nails", "KMFDM", "Marilyn Manson"})

    def test_does_not_return_artist_who_has_no_songs(self, fixtures: Fixtures) -> None:
        # given the artist who has no songs
        songs = LibraryItem.objects.filter(artist="Artist 4")
        songs.delete()

        # given the queryset
        queryset = LibraryItem.objects.all()

        # when we call the mood strategy with 1 entry needed
        station = Station.main_station()
        with patch("teamplayer.lib.autofill.settings") as settings:
            settings.AUTOFILL_MOOD_TOP_ARTISTS = 3
            settings.AUTOFILL_MOOD_HISTORY = 86400
            result = auto_fill_mood(
                entries_needed=1, queryset=queryset, station=station
            )

        # then obviouly we don't get the top artist because he has no
        # songs
        self.assertEqual(len(result), 1)
        song = result[0]
        self.assertNotEqual(song.artist, "Artist 4")

    def test_returns_random_artist_song_when_not_enough_artists(
        self, fixtures: Fixtures
    ) -> None:
        # given the queryset
        queryset = LibraryItem.objects.all()

        # when we call the mood strategy with 4 entries needed, but only the
        # top 3 considered
        station = Station.main_station()
        with patch("teamplayer.lib.autofill.settings") as settings:
            settings.AUTOFILL_MOOD_TOP_ARTISTS = 3
            settings.AUTOFILL_MOOD_HISTORY = 3600
            result = auto_fill_mood(
                entries_needed=4, queryset=queryset, station=station
            )

        # then it gives us the songs by the top 3 artists and another artist
        self.assertEqual(len(result), 4)
        artists = set(i.artist for i in result)
        self.assertGreater(artists, {"KMFDM", "Nine Inch Nails", "Marilyn Manson"})


class TagsTest(TestCase):
    """tests for the autofill_from_tags strategy"""

    def test_auto_fill_from_tags(self):
        # given the (mock) queryset
        queryset = MagicMock(name="queryset")
        queryset.count = Mock(return_value=90)
        queryset.filter = MagicMock(return_value=queryset)

        # given the player
        player = Player.objects.create_player("test_player", password="test")

        # given the station with a tag in the name
        station = Station.objects.create(creator=player, name="#electronic")

        # when we call auto_fill_from_tags()
        with patch("teamplayer.models.lib.songs.pylast.Tag") as Tag:
            with utils.getdata("electronic_tags.pickle", "rb") as fp:
                tags = pickle.load(fp)
            Tag().get_top_artists.return_value = tags
            Tag.reset_mock()

            result = auto_fill_from_tags(
                entries_needed=3, queryset=queryset, station=station
            )

        # then the queryset is filtered on the artists from the tags
        artists = songslib.artists_from_tags(["electronic"])
        queryset.filter.assert_called_with(artist__in=artists)

        # and 3 items are returned
        self.assertEqual(len(result), 3)

    def test_when_more_tagged_songs_than_needed(self):
        # given queryset
        queryset = LibraryItem.objects.all()

        # given the player
        player = Player.objects.create_player("test_player", password="test")

        # given the station with a tag in the name
        station = Station.objects.create(creator=player, name="#electronic")

        # when we call auto_fill_from_tags()
        with patch("teamplayer.lib.autofill.artists_from_tags") as p:
            p.return_value = [i.artist for i in queryset]

            result = auto_fill_from_tags(
                entries_needed=20, queryset=queryset, station=station
            )

        # then it returns all the songs in the queryset
        self.assertEqual(set(result), set(queryset))

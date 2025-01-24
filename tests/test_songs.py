import json
import pickle
from unittest.mock import Mock, patch

import pylast
from django.test import TestCase
from django.urls import reverse

from teamplayer.lib import songs
from teamplayer.models import Entry, Mood, Player, Station

from . import utils


class AutoFindSong(TestCase):
    def setUp(self):
        # create a player
        self.player = Player.objects.create_player("test", password="test")
        self.client.login(username="test", password="test")
        self.url = reverse("home")

        with patch("teamplayer.lib.mpc.MPC") as mpc:
            mpc.return_value.http_port = 8002
            mpc.return_value.currently_playing.return_value = {}
            self.client.get(self.url)

        self.main_station = Station.main_station()

    @patch("teamplayer.lib.songs.get_similar_artists")
    def test(self, get_similar_artists):
        with utils.getdata("prince_similar.json") as fp:
            get_similar_artists.return_value = json.load(fp)

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(station=self.main_station, artist="Prince")

        # And the entries
        Entry.objects.create(
            artist="Elliott Smith",
            title="Happiness",
            queue=queue,
            station=self.main_station,
        )
        purple_rain = Entry.objects.create(
            artist="Prince", title="Purple Rain", queue=queue, station=self.main_station
        )

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, self.main_station)

        # Then we should get purple_rain
        self.assertEqual(song, purple_rain)

    @patch("teamplayer.lib.songs.get_similar_artists")
    def test_no_songs_returns_None(self, get_similar_artists):
        with utils.getdata("prince_similar.json") as fp:
            get_similar_artists.return_value = json.load(fp)

        # Given the player's empty queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # And Current mood
        Mood.objects.create(station=self.main_station, artist="Prince")

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, self.main_station)

        # Then we get nothing
        self.assertEqual(song, None)

    @patch("teamplayer.lib.songs.get_similar_artists")
    def test_no_mood_fits_returns_first_entry(self, get_similar_artists):
        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(station=self.main_station, artist="Prince")

        # And the entries that don't fit the mood
        happiness = Entry.objects.create(
            artist="Elliott Smith",
            title="Happiness",
            queue=queue,
            station=self.main_station,
        )
        Entry.objects.create(
            artist="Metallica",
            title="Fade to Black",
            queue=queue,
            station=self.main_station,
        )

        # When we call auto_find_song
        get_similar_artists.return_value = []
        song = songs.auto_find_song(None, queue, self.main_station)

        # Then we should get happiness
        self.assertEqual(song, happiness)

    @patch("teamplayer.lib.songs.get_similar_artists")
    def test_does_not_return_previous_artist(self, get_similar_artists):
        with utils.getdata("prince_similar.json") as fp:
            get_similar_artists.return_value = json.load(fp)

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(station=self.main_station, artist="Prince")

        # And the entries with a song that fits the mood
        Entry.objects.create(
            artist="Prince", title="Purple Rain", queue=queue, station=self.main_station
        )
        metallica = Entry.objects.create(
            artist="Metallica",
            title="Fade to Black",
            queue=queue,
            station=self.main_station,
        )

        # When we call auto_find_song with a previous artist being the one that
        # fits the mood
        song = songs.auto_find_song("Prince", queue, self.main_station)

        # Then instead of Prince we should get Metallica
        self.assertEqual(song, metallica)


class ScrobbleSongTest(TestCase):
    def test_now_playing(self):
        # given the song dict
        song = {
            "artist": "Prince",
            "title": "Purple Rain",
            "album": "Purple Rain",
            "total_time": 190,
        }

        # when we call scrobble_song() with now_playing=True
        with patch("teamplayer.lib.songs.pylast.LastFMNetwork") as Network:
            songs.scrobble_song(song, now_playing=True)

        # then it makes the appropriate call to the scrobbler
        Network.return_value.update_now_playing.assert_called_with(
            "Prince", "Purple Rain", album="Purple Rain", duration=190
        )

    def test_not_now_playing(self):
        # given the song dict
        song = {
            "artist": "Prince",
            "title": "Purple Rain",
            "album": "Purple Rain",
            "total_time": 190,
        }

        # when we call scrobble_song() with now_playing=False
        with patch("teamplayer.lib.songs.pylast.LastFMNetwork") as Network:
            with patch("teamplayer.lib.songs.now") as now:
                songs.scrobble_song(song, now_playing=False)

        # then it makes the appropriate call to the scrobbler
        timestamp = int(now().timestamp()) - 190
        Network.return_value.scrobble.assert_called_with(
            "Prince", "Purple Rain", timestamp, album="Purple Rain", duration=190
        )

    def test_returns_True_on_success(self):
        # given the song dict
        song = {
            "artist": "Prince",
            "title": "Purple Rain",
            "album": "Purple Rain",
            "total_time": 190,
        }

        # when we call scrobble_song()
        with patch("teamplayer.lib.songs.pylast.LastFMNetwork"):
            result = songs.scrobble_song(song, now_playing=True)

        # then True is returned
        self.assertEqual(result, True)

    def test_returns_False_on_failure(self):
        # given the song dict
        song = {
            "artist": "Prince",
            "title": "Purple Rain",
            "album": "Purple Rain",
            "total_time": 190,
        }

        # when we call scrobble_song() and an error is raised by pylast
        with patch("teamplayer.lib.songs.pylast.LastFMNetwork") as Network:
            exc = pylast.WSError(Network(), "fail", "You suck")
            Network.return_value.update_now_playing.side_effect = exc
            result = songs.scrobble_song(song, now_playing=True)

        # then False is returned
        self.assertEqual(result, False)


class TopArtistsFromTag(TestCase):
    def test_respects_limit(self):
        # set up our mock object
        with patch("teamplayer.lib.songs.pylast.Tag") as Tag:
            with utils.getdata("electronic_tags.pickle", "rb") as fp:
                tags = pickle.load(fp)
            Tag().get_top_artists.return_value = tags
            Tag.reset_mock()

            # when we call top_artists_from_tag() with a limit
            songs.top_artists_from_tag("electronic", limit=5)

        # then it only asks lastfm for the top 5 tasks
        Tag().get_top_artists.assert_called_with(limit=5)

    def test_call(self):
        # set up our mock object
        with patch("teamplayer.lib.songs.pylast.Tag") as Tag:
            with utils.getdata("electronic_tags.pickle", "rb") as fp:
                tags = pickle.load(fp)
            Tag().get_top_artists.return_value = tags
            Tag.reset_mock()

            # when we call top_artists_from_tag()
            result = songs.top_artists_from_tag("electronic")

        # then we get the top artists
        expected = [x.item.name for x in tags]
        self.assertEqual(result, expected)

    def test_no_tag_with_that_name(self):
        # given the non-existent tag name
        tag_name = "#post-grunge"

        # when we call top_artists_from_tag()
        # (pytag will raise an exception
        with patch("teamplayer.lib.songs.pylast.Tag") as Tag:
            Tag.get_top_artists.side_effect = pylast.WSError(
                None, "6", "No tag with that name"
            )
            result = songs.top_artists_from_tag(tag_name)

        # then we get an empty list
        self.assertEqual(result, [])


class ArtistsFromTagsTest(TestCase):
    def test_call(self):
        # set up our mock object
        tags = {}
        with utils.getdata("electronic_tags.pickle", "rb") as fp:
            tags["electronic"] = pickle.load(fp)
        with utils.getdata("canadian_tags.pickle", "rb") as fp:
            tags["canadian"] = pickle.load(fp)

        with patch("teamplayer.lib.songs.pylast.Tag") as Tag:

            def side_effect(tag, *args, **kwargs):
                pylast_tag = Mock()
                pylast_tag.get_top_artists.return_value = tags.get(tag, [])

                return pylast_tag

            Tag.side_effect = side_effect

            # when we call artists from tags
            result = songs.artists_from_tags(["canadian", "electronic"])

        # Then we only get the list of canadian electronic artists
        self.assertEqual(set(result), set(["Grimes", "Caribou"]))


class SplitTagIntoWordsTest(TestCase):
    def test_loveSongs(self):
        result = songs.split_tag_into_words("loveSongs")
        self.assertEqual(result, "love songs")

    def test_LoveSongs(self):
        result = songs.split_tag_into_words("LoveSongs")
        self.assertEqual(result, "love songs")

    def test_lovesongs(self):
        result = songs.split_tag_into_words("LoveSongs")
        self.assertEqual(result, "love songs")

    def test_LOVESONGS(self):
        result = songs.split_tag_into_words("LOVESONGS")
        self.assertEqual(result, "lovesongs")

    def test_love_songs(self):
        result = songs.split_tag_into_words("love_songs")
        self.assertEqual(result, "love songs")

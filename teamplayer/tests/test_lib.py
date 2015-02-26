"""Unit tests for TeamPlayer lib functions"""
from unittest import mock

import django.contrib.auth.models
import django.core.urlresolvers
import django.test

import teamplayer.models
from teamplayer import version_string
from teamplayer.tests import utils

ARTIST_XML = utils.ARTIST_XML
SILENCE = utils.SILENCE
PRINCE_SIMILAR_TXT = utils.PRINCE_SIMILAR_TXT
Mood = teamplayer.models.Mood
TestCase = django.test.TestCase
patch = mock.patch
reverse = django.core.urlresolvers.reverse


class Lib(TestCase):

    """Test the main lib"""
    def test_random_filename(self):
        first = teamplayer.lib.get_random_filename()
        second = teamplayer.lib.get_random_filename()
        self.assertEqual(type(first), str)
        self.assertEqual(type(second), str)
        self.assertNotEqual(first, second)


class LibSongs(TestCase):

    """Test the songs lib"""

    @patch('teamplayer.lib.websocket.IPCHandler.send_message')
    def setUp(self, mock):
        self.user_data = {
            'username': 'br',
            'password': 'blah blah',
        }

        self.player = teamplayer.models.Player.objects.create_player(
            **self.user_data)
        self.user = self.player.user
        song = open(SILENCE, 'rb')
        view = reverse('teamplayer.views.add_to_queue')

        self.client.login(username=self.user_data['username'],
                          password=self.user_data['password'])
        self.client.post(view, {'song': song}, follow=True)

    def test_can_get_metadata(self):
        metadata = teamplayer.lib.songs.get_song_metadata(SILENCE)
        self.assertEqual(
            metadata,
            (u'TeamPlayer', u'Station Break', 'mp3')
        )

    def test_invalid_file(self):
        self.assertRaises(
            teamplayer.lib.songs.SongMetadataError,
            teamplayer.lib.songs.get_song_metadata, __file__
        )

    def test_time_to_secs(self):
        func = teamplayer.lib.songs.time_to_secs
        self.assertEqual(func('00:05'), 5)
        self.assertEqual(func('9:01'), 541)
        self.assertEqual(func('9:00:01'), 32401)

    @patch('teamplayer.lib.songs.urllib.request.urlopen')
    def test_artist_image_url(self, mock):
        mock.return_value = open(ARTIST_XML)
        url = teamplayer.lib.songs.get_image_url_for('Prince')
        self.assertEqual(url,
                         'http://userserve-ak.last.fm/serve/252/609358.jpg')

    @patch('teamplayer.lib.songs.urllib.request.urlopen')
    def test_blank_artist(self, mock):
        """Demonstrate we get the "clear" image for blank artists"""
        # given a blank artist
        blank_artist = ''

        # when we call the the function
        result = teamplayer.lib.songs.get_image_url_for(blank_artist)

        # then we get a clear image url
        self.assertEqual(result, teamplayer.lib.songs.CLEAR_IMAGE_URL)

    def test_find_a_song(self):
        """Test that it can find songs in the queue"""
        station = teamplayer.models.Station.main_station()
        song = teamplayer.lib.songs.find_a_song([self.player], station)
        self.assertEqual(type(song), teamplayer.models.Entry)
        song.delete()
        song = teamplayer.lib.songs.find_a_song([self.player], station)
        self.assertEqual(song, None)


class MoodTestCase(TestCase):
    """Test the Mood model."""
    @patch('teamplayer.lib.songs.urlopen')
    def test_mood(self, mock):
        mock.return_value = open(PRINCE_SIMILAR_TXT, 'rb')
        station = teamplayer.models.Station.main_station()
        self.assertEqual(Mood.objects.all().count(), 0)
        Mood.log_mood('Prince', station)
        self.assertNotEqual(Mood.objects.all().count(), 0)
        prince = Mood.objects.filter(artist='Prince', station=station)
        self.assertEqual(prince.count(), 1)
        the_time = Mood.objects.filter(artist='The Time', station=station)
        self.assertTrue(the_time.exists())


class FirstOrNoneTest(TestCase):
    """
    Demonstrate the first_or_none() function.
    """
    def setUp(self):
        self.empty_dict = {}
        self.dict_with_list = {'denoms': [1, 5, 10, 20]}
        self.dict_with_empty_list = {'empty': []}
        self.dict_with_nonlist = {'here': 'there'}

    def test_empty_dict(self):
        self.assertEqual(
            teamplayer.lib.first_or_none(
                self.empty_dict,
                'bogus'
            ),
            None
        )

    def test_dict_with_list(self):
        self.assertEqual(
            teamplayer.lib.first_or_none(
                self.dict_with_list,
                'denoms'
            ),
            1
        )

        self.assertEqual(
            teamplayer.lib.first_or_none(
                self.dict_with_list,
                'bogus'
            ),
            None
        )

    def test_dict_with_empty_list(self):
        self.assertEqual(
            teamplayer.lib.first_or_none(
                self.dict_with_empty_list,
                'empty'
            ),
            None
        )

    def test_dict_with_nonlist(self):
        self.assertEqual(
            teamplayer.lib.first_or_none(
                self.dict_with_nonlist,
                'here'
            ),
            'there'
        )


class VersionStringTest(TestCase):
    """Tests for version_string()"""
    # While not a part of lib., per-se, this is probably the best place to put
    # it instead of creating a new module just for one function
    def test_show_revision(self):
        # Given the version tuple
        version = (2, 0, 0, 'final')

        # When we call version_string() on it
        result = version_string(version, show_revision=True)

        # Then we get the expected string
        self.assertRegex(result, r'^2\.0\.0 \([0-9a-f]+')

    def test_final(self):
        # Given the version tuple with "final" in it
        version = (2, 0, 0, 'final')

        # When we call version_string() on it
        result = version_string(version, show_revision=False)

        # Then we get the expected string
        expected = '2.0.0'
        self.assertEqual(result, expected)

    def test_not_final(self):
        # Given the version tuple without "final" in it
        version = (2, 0, 0, 'beta1')

        # When we call version_string() on it
        result = version_string(version, show_revision=False)

        # Then we get the expected string
        expected = '2.0.0-beta1'
        self.assertEqual(result, expected)

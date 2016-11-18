"""Unit tests for TeamPlayer lib functions"""
import json
from unittest import mock

import django.contrib.auth.models
import django.core.urlresolvers
import django.test

import teamplayer.models
from teamplayer import version_string
from teamplayer.conf import settings
from teamplayer.tests import utils

SILENCE = utils.SILENCE
Mood = teamplayer.models.Mood
TestCase = django.test.TestCase
call = mock.call
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
        view = reverse('add_to_queue')

        self.client.login(username=self.user_data['username'],
                          password=self.user_data['password'])
        self.client.post(view, {'song': song}, follow=True)

    def test_can_get_metadata(self):
        metadata = teamplayer.lib.songs.get_song_metadata(SILENCE)
        self.assertEqual(
            metadata,
            {'artist': 'TeamPlayer',
             'title': 'Station Break',
             'type': 'mp3',
             'mimetype': 'audio/mp3'}
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

    @patch('teamplayer.lib.songs.pylast.LastFMNetwork')
    def test_artist_image_url(self, LastFMNetwork):
        img_url = 'http://userserve-ak.last.fm/serve/252/609358.jpg'
        network = LastFMNetwork()
        prince = network.get_artist('Prince')
        prince.get_cover_image.return_value = img_url
        LastFMNetwork.reset_mock()

        url = teamplayer.lib.songs.get_image_url_for('Prince')
        self.assertEqual(url, img_url)
        expected = call(api_key=settings.LASTFM_APIKEY).get_artist(
            'Prince').get_cover_image()
        expected = expected.call_list()
        self.assertEqual(LastFMNetwork.mock_calls, expected)

    def test_blank_artist(self):
        """Demonstrate we get the "clear" image for blank artists"""
        # given a blank artist
        blank_artist = ''

        # when we call the the function
        result = teamplayer.lib.songs.get_image_url_for(blank_artist)

        # then we get a clear image url
        self.assertEqual(result, teamplayer.lib.songs.CLEAR_IMAGE_URL)

    @patch('teamplayer.lib.songs.pylast.LastFMNetwork')
    def test_lastfm_image_is_none(self, LastFMNetwork):
        # given the artist for which lastfm has no image
        artist = 'Albert Hopkins'
        LastFMNetwork().get_artist().get_cover_image.return_value = None
        LastFMNetwork.reset_mock()

        # when we call the function
        result = teamplayer.lib.songs.get_image_url_for(artist)

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
    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_mood(self, get_similar_artists):
        with utils.getdata('prince_similar.json') as fp:
            get_similar_artists.return_value = json.load(fp)
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


class AttemptFileRenameTest(TestCase):
    """Tests for the attempt_file_rename() function"""

    def test_call(self):
        # given the filename which cannot be encoded as utf-8
        filename = '/tmp/Kass\udce9 Mady Diabat\udce9 - Ko Kuma Magni.mp3'

        # when we call attempt_file_rename() on it
        new_name = teamplayer.lib.attempt_file_rename(filename)

        # then we get the expected result
        self.assertEqual(
            new_name, '/tmp/Kassé Mady Diabaté - Ko Kuma Magni.mp3')

    def test_original_name_is_ok(self):
        # given the filename which is already fine as utf-8
        filename = '/tmp/nothing_wrong_with_me.mp3'

        # when we call attempt_file_rename() on it
        new_name = teamplayer.lib.attempt_file_rename(filename)

        # then it returns None because the file was not renamed
        self.assertEqual(new_name, None)

    def test_dirname_is_bad(self):
        # given the filename with a directory path that is unencodable
        filename = '/tmp/t\udce9st/fil\udce9.mp3'

        # when we call attempt_file_rename() on it
        new_name = teamplayer.lib.attempt_file_rename(filename)

        # then it returns None because the directory is still bad and we don't
        # rename directories
        self.assertEqual(new_name, None)

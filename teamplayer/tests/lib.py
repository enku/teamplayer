"""Unit tests for TeamPlayer lib functions"""
import django.test
import django.core.urlresolvers
import django.contrib.auth.models

import mock

import teamplayer.lib
import teamplayer.models

from teamplayer.tests import utils

IMAGES_XML = utils.IMAGES_XML
SILENCE = utils.SILENCE
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

        self.user = teamplayer.lib.users.create_user(**self.user_data)
        song = open(SILENCE)
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

    @patch('urllib.urlopen')
    def test_artist_image_url(self, mock):
        mock.return_value = open(IMAGES_XML)
        self.assertFalse('Prince' in teamplayer.lib.songs.ARTIST_IMAGE_CACHE)
        url = teamplayer.lib.songs.get_image_url_for('Prince')
        self.assertEqual(url,
                         'http://userserve-ak.last.fm/serve/126s/231717.jpg')

    @patch('urllib.urlopen')
    def test_blank_artist(self, mock):
        """Demonstrate we get the "clear" image for blank artists"""
        # given a blank artist
        blank_artist = ''

        # when we call the the function
        result = teamplayer.lib.songs.get_image_url_for(blank_artist)

        # then we get a clear image url
        self.assertEqual(result, teamplayer.lib.songs.CLEAR_IMAGE_URL)

    def test_mood(self):
        station = teamplayer.models.Station.main_station()
        self.assertEqual(Mood.objects.all().count(), 0)
        teamplayer.lib.songs.log_mood('Prince', station)
        self.assertNotEqual(Mood.objects.all().count(), 0)
        prince = Mood.objects.filter(artist='Prince', station=station)
        self.assertEqual(prince.count(), 1)
        the_time = Mood.objects.filter(artist='The Time', station=station)
        self.assertTrue(the_time.exists())

    def test_find_a_song(self):
        """Test that it can find songs in the queue"""
        station = teamplayer.models.Station.main_station()
        song = teamplayer.lib.songs.find_a_song([self.user], station)
        self.assertEqual(type(song), teamplayer.models.Entry)
        song.delete()
        song = teamplayer.lib.songs.find_a_song([self.user], station)
        self.assertEqual(song, None)


class LibUsers(TestCase):

    """Test the songs lib"""

    def test_create_user(self):
        teamplayer.lib.users.create_user(username='test', password='test')

        user = django.contrib.auth.models.User.objects.get(username='test')
        profile = user.get_profile()
        self.assertEqual(profile.queue.entry_set.count(), 0)


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

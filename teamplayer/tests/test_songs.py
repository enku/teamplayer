from io import BytesIO
from unittest.mock import patch

from django.core.urlresolvers import reverse
from django.test import TestCase

from teamplayer import scrobbler
from teamplayer.lib import songs
from teamplayer.models import MAIN_STATION, Entry, Mood, Player
from teamplayer.tests import utils

PRINCE_SIMILAR_TXT = utils.PRINCE_SIMILAR_TXT


class ScrobbleSongError(TestCase):
    """
    Demonstrate the ProtocolError thrown during scrobble_song
    """
    @patch('teamplayer.scrobbler.login')
    def test_error(self, mock_login):
        # given the "song"
        song = {
            'artist': 'Prince',
            'title': 'Purple Rain',
            'total_time': 500,
        }

        # when we scrobble it and the scrobbler raises an error
        mock_login.side_effect = scrobbler.ProtocolError
        status = songs.scrobble_song(song)

        # Then the exception is not propogated and we just get a False return
        self.assertEqual(status, False)


class AutoFindSong(TestCase):
    def setUp(self):
        # create a player
        self.player = Player.objects.create_player('test', password='test')
        self.client.login(username='test', password='test')
        self.url = reverse('teamplayer.views.home')
        self.client.get(self.url)

    @patch('teamplayer.lib.songs.urllib.request.urlopen')
    def test(self, mock_open):
        mock_open.return_value = open(PRINCE_SIMILAR_TXT, 'rb')

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(
            station=MAIN_STATION,
            artist='Prince',
        )

        # And the entries
        Entry.objects.create(
            artist='Elliott Smith',
            title='Happiness',
            queue=queue,
            station=MAIN_STATION
        )
        purple_rain = Entry.objects.create(
            artist='Prince',
            title='Purple Rain',
            queue=queue,
            station=MAIN_STATION
        )

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, MAIN_STATION)

        # Then we should get purple_rain
        self.assertEqual(song, purple_rain)

    @patch('teamplayer.lib.songs.urllib.request.urlopen')
    def test_no_songs_returns_None(self, mock_open):
        mock_open.return_value = open(PRINCE_SIMILAR_TXT, 'rb')

        # Given the player's empty queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # And Current mood
        Mood.objects.create(
            station=MAIN_STATION,
            artist='Prince',
        )

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, MAIN_STATION)

        # Then we get nothing
        self.assertEqual(song, None)

    @patch('teamplayer.lib.songs.urllib.request.urlopen')
    def test_no_mood_fits_returns_first_entry(self, mock_open):
        mock_open.return_value = BytesIO()

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(
            station=MAIN_STATION,
            artist='Prince',
        )

        # And the entries that don't fit the mood
        happiness = Entry.objects.create(
            artist='Elliott Smith',
            title='Happiness',
            queue=queue,
            station=MAIN_STATION
        )
        Entry.objects.create(
            artist='Metallica',
            title='Fade to Black',
            queue=queue,
            station=MAIN_STATION
        )

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, MAIN_STATION)

        # Then we should get happiness
        self.assertEqual(song, happiness)

    @patch('teamplayer.lib.songs.urllib.request.urlopen')
    def test_does_not_return_previous_artist(self, mock_open):
        mock_open.return_value = open(PRINCE_SIMILAR_TXT, 'rb')

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(
            station=MAIN_STATION,
            artist='Prince',
        )

        # And the entries with a song that fits the mood
        Entry.objects.create(
            artist='Prince',
            title='Purple Rain',
            queue=queue,
            station=MAIN_STATION
        )
        metallica = Entry.objects.create(
            artist='Metallica',
            title='Fade to Black',
            queue=queue,
            station=MAIN_STATION
        )

        # When we call auto_find_song with a previous artist being the one that
        # fits the mood
        song = songs.auto_find_song('Prince', queue, MAIN_STATION)

        # Then instead of Prince we should get Metallica
        self.assertEqual(song, metallica)

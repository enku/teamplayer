import json
from unittest.mock import patch

from django.core.urlresolvers import reverse
from django.test import TestCase

from teamplayer.lib import songs
from teamplayer.models import Entry, Mood, Player, Station
from teamplayer.tests import utils

PRINCE_SIMILAR_TXT = utils.PRINCE_SIMILAR_TXT


class AutoFindSong(TestCase):
    def setUp(self):
        # create a player
        self.player = Player.objects.create_player('test', password='test')
        self.client.login(username='test', password='test')
        self.url = reverse('teamplayer.views.home')
        self.client.get(self.url)

        self.main_station = Station.main_station()

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test(self, get_similar_artists):
        with utils.getdata('prince_similar.json') as fp:
            get_similar_artists.return_value = json.load(fp)

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(
            station=self.main_station,
            artist='Prince',
        )

        # And the entries
        Entry.objects.create(
            artist='Elliott Smith',
            title='Happiness',
            queue=queue,
            station=self.main_station
        )
        purple_rain = Entry.objects.create(
            artist='Prince',
            title='Purple Rain',
            queue=queue,
            station=self.main_station
        )

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, self.main_station)

        # Then we should get purple_rain
        self.assertEqual(song, purple_rain)

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_no_songs_returns_None(self, get_similar_artists):
        with utils.getdata('prince_similar.json') as fp:
            get_similar_artists.return_value = json.load(fp)

        # Given the player's empty queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # And Current mood
        Mood.objects.create(
            station=self.main_station,
            artist='Prince',
        )

        # When we call auto_find_song
        song = songs.auto_find_song(None, queue, self.main_station)

        # Then we get nothing
        self.assertEqual(song, None)

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_no_mood_fits_returns_first_entry(self, get_similar_artists):
        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(
            station=self.main_station,
            artist='Prince',
        )

        # And the entries that don't fit the mood
        happiness = Entry.objects.create(
            artist='Elliott Smith',
            title='Happiness',
            queue=queue,
            station=self.main_station
        )
        Entry.objects.create(
            artist='Metallica',
            title='Fade to Black',
            queue=queue,
            station=self.main_station
        )

        # When we call auto_find_song
        get_similar_artists.return_value = []
        song = songs.auto_find_song(None, queue, self.main_station)

        # Then we should get happiness
        self.assertEqual(song, happiness)

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_does_not_return_previous_artist(self, get_similar_artists):
        with utils.getdata('prince_similar.json') as fp:
            get_similar_artists.return_value = json.load(fp)

        # Given the player's queue...
        self.player.auto_mode = True
        self.player.save()
        queue = self.player.queue

        # Current mood...
        Mood.objects.create(
            station=self.main_station,
            artist='Prince',
        )

        # And the entries with a song that fits the mood
        Entry.objects.create(
            artist='Prince',
            title='Purple Rain',
            queue=queue,
            station=self.main_station
        )
        metallica = Entry.objects.create(
            artist='Metallica',
            title='Fade to Black',
            queue=queue,
            station=self.main_station
        )

        # When we call auto_find_song with a previous artist being the one that
        # fits the mood
        song = songs.auto_find_song('Prince', queue, self.main_station)

        # Then instead of Prince we should get Metallica
        self.assertEqual(song, metallica)

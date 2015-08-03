"""Unit tests for the async module"""
from unittest.mock import patch
from unittest import skip

from django.test import TestCase

from teamplayer.lib import async
from teamplayer.lib.mpc import MPC
from teamplayer.models import Mood, Player, Station


class ScrobbleSongTest(TestCase):
    """Tests for the async.scrobble_song function"""

    def test_calls_scrobbler(self):
        # given the player
        self.player = Player.objects.create_player('test_player',
                                                   password='***')
        # given the main station
        main_station = Station.main_station()

        # given the song_info dict
        song_info = {'artist': 'Prince',
                     'title': 'Purple Rain',
                     'station_id': main_station.pk,
                     'player': self.player.username}

        # when we call scrobble_song
        with patch('teamplayer.lib.async.songs.scrobble_song') as mock_scrob:
            async.scrobble_song(
                sender=main_station, previous_song=song_info, current_song=None)

        # then the scrobbler is called with the expected args
        mock_scrob.assert_called_with(song_info, now_playing=False)

    def test_called_not_main_station(self):
        # given the player
        self.player = Player.objects.create_player('test_player',
                                                   password='***')
        # given the station that's not the main station
        station = Station()
        station.creator = self.player
        station.name = 'test station'
        station.save()

        # given the song_info dict
        song_info = {'artist': 'Prince',
                     'title': 'Purple Rain',
                     'station_id': station.pk,
                     'player': self.player.username}

        # when we call scrobble_song
        with patch('teamplayer.lib.async.songs.scrobble_song') as mock_scrob:
            async.scrobble_song(
                sender=station, previous_song=None, current_song=song_info)

        # then the scrobbler is not called
        self.assertEqual(mock_scrob.mock_calls, [])


class LogMoodTest(TestCase):
    """Tests for the async.log_mood function"""
    def test_call(self):
        # given the player
        player = Player.objects.create_player('test_player', password='***')
        # given the station
        station = Station.main_station()

        # given the song_info dict
        song_info = {
            'artist': 'Madonna',
            'title': 'True Blue',
            'file': '{0}-123456789.mp3'.format(player.pk),
            'dj': '',
            'player_id': player.pk
        }

        # when we call log_mood
        async.log_mood(sender=station, current_song=song_info)

        # then a mood is added
        query = Mood.objects.filter(artist='Madonna', station=station)
        self.assertEqual(query.count(), 1)

    def test_unknown(self):
        # given the player
        player = Player.objects.create_player('test_player', password='***')

        # given the station
        station = Station.main_station()

        # given the song_info with "Unknown" artist
        song_info = {
            'artist': 'Unknown',
            'title': 'Hidden Track',
            'file': '{0}-123456789.mp3'.format(player.pk),
            'player_id': '1',
            'dj': ''
        }

        # when we call log_mood
        async.log_mood(sender=station, current_song=song_info)

        # then a mood is not added
        query = Mood.objects.all()
        self.assertEqual(query.count(), 0)

    def test_doesnt_log_django(self):
        # given the DJ Ango Player
        dj_ango = Player.dj_ango()

        # given the station
        station = Station.main_station()

        # given the song_info from DJ Ango
        song_info = {
            'artist': 'Limp Bizkit',
            'title': 'Break Stuff',
            'file': '{0}-123456789.mp3'.format(dj_ango.pk),
            'player_id': str(dj_ango.pk),  # the sticker is a string object
            'dj': 'DJ Ango'
        }

        # when we call log_mood
        async.log_mood(sender=station, current_song=song_info)

        # then a mood is not added
        query = Mood.objects.all()
        self.assertEqual(query.count(), 0)


@patch('teamplayer.lib.async.MPC', spec=MPC)
class StationThread(TestCase):
    """Tests for the StationThread"""
    def test_station_attr(self, mock_mpc):
        # given the station
        station = Station.main_station()

        try:
            # when we create a station off that thread
            thread = async.StationThread(station=station)

            # then it has a station attribute
            self.assertEqual(thread.station, station)
        finally:
            thread.running = False

    def test_starts_mpd(self, mock_mpc):
        # given the station
        station = Station.main_station()

        try:
            # when we create a station off that thread
            thread = async.StationThread(station=station)

            # then it starts an mpd
            self.assertTrue(mock_mpc.called)
            self.assertTrue(mock_mpc.return_value.create_config.called)
            self.assertTrue(mock_mpc.return_value.start.called)
        finally:
            thread.running = False

    def test_stop(self, mock_mpc):
        # given the station
        station = Station.main_station()

        try:
            # given the station thread
            thread = async.StationThread(station=station)

            # when we call .stop() on the thread
            thread.stop()

            # then it stops the mpd
            self.assertTrue(mock_mpc.return_value.stop.called)
        finally:
            thread.running = False

    @skip('This test passes but the thread blows up and it is ugly.')
    def test_exception_logging_self(self, mock_mpc):
        # given the station
        station = Station.main_station()

        try:
            # when an exception is raised inside the thread
            with patch(
                'teamplayer.lib.async.StationThread.wait_for'
            ) as wait_for:
                wait_for.side_effect = Exception

                with patch('teamplayer.lib.async.logger') as logger:
                    thread = async.StationThread(station=station)
                    try:
                        # given the station thread
                        thread.start()
                        thread.join()
                    except Exception:
                        pass

            # then it stops the mpd
            logger.exception.assert_called_with(
                'Station {}: Error inside main loop'.format(station.id))
            self.assertTrue(logger.error.called)
        finally:
            thread.stop()

"""Tests for the MPC client"""
import os
import time
from io import BytesIO
from unittest.mock import Mock, call, patch

from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase
from mpd import ConnectionError, MPDClient

from teamplayer.lib.mpc import MPC
from teamplayer.lib.songs import CLEAR_IMAGE_URL
from teamplayer.models import Entry, Player, Station


@patch('teamplayer.lib.mpc.mpd.MPDClient', autospec=MPDClient)
class MPCTest(TestCase):
    def setUp(self):
        self.station = Station.main_station()
        self.mpc = MPC(self.station)
        self.filename = os.path.join(
            os.path.dirname(__file__), 'data', 'silence.mp3')
        self.player = Player.objects.create_player('test_player')
        self.player.dj_name = 'MCA'
        self.player.save()

    def tearDown(self):
        for f in [self.mpc.pid_file, self.mpc.db_file]:
            if os.path.exists(f):
                os.unlink(f)

    def test_start(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call mpc.start()
        with patch('teamplayer.lib.mpc.subprocess.Popen') as mock_popen:
            mpc.start()

        # then it calls mpd with the appropriate config
        expected = call(('mpd', '--no-daemon', mpc.conf_file))
        self.assertEqual(mock_popen.mock_calls, [expected])

        # and it makes the expected calls to mpc
        self.assertTrue(call().update() in mpd_client.mock_calls)
        self.assertTrue(call().consume(1) in mpd_client.mock_calls)
        self.assertTrue(call().play() in mpd_client.mock_calls)

    def test_stop(self, mpd_client):
        # given the mpc instance that is "running"
        mpc = self.mpc
        mpc.mpd = mock_mpd = Mock()

        # when we call mpc.stop()
        mpc.stop()

        # then it terminates the mpd process
        self.assertTrue(mock_mpd.terminate.called)

    def test_create_config(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        if os.path.exists(mpc.conf_file):
            os.unlink(mpc.conf_file)

        # when we call create_config()
        mpc.create_config()

        # then it creates a config file
        self.assertTrue(os.path.exists(mpc.conf_file))

    def test_currently_playing(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call .currently_playing()
        config = {
            'status.return_value':
                {'state': 'play', 'time': '100:300', 'remaining_time': '0:15'},
            'currentsong.return_value':
                {'file': '1-t.mp3', 'artist': 'Prince', 'title': 'Purple Rain'},
            'sticker_list.return_value': {'dj': '', 'player_id': 1}
        }
        mpd_client.return_value.configure_mock(**config)
        result = mpc.currently_playing()

        # then we get the expected result
        expected = {
            'artist': 'Prince',
            'title': 'Purple Rain',
            'artist_image': '/artist/Prince/image',
            'total_time': 300,
            'remaining_time': 200,
            'station_id': self.station.pk,
            'dj': ''
        }
        self.assertEqual(result, expected)

    def test_currently_playing_no_artist(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call .currently_playing() and mpd's currentsong returns not
        # "artist" key
        config = {
            'currentsong.return_value':
                {'file': '1-silence.mp3', 'title': 'Purple Rain'},
            'status.return_value':
                {'state': 'play', 'time': '100:300', 'remaining_time': '0:15'},
            'sticker_list.return_value': {'dj': '', 'player_id': 1}
        }
        mpd_client.return_value.configure_mock(**config)
        result = mpc.currently_playing()

        # then we get the expected dict with "artist" set to None
        expected = {
            'artist': None,
            'title': 'Purple Rain',
            'artist_image': CLEAR_IMAGE_URL,
            'total_time': 300,
            'remaining_time': 200,
            'station_id': self.station.pk,
            'dj': ''
        }
        self.assertEqual(result, expected)

    def test_currently_playing_no_title(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call .currently_playing() and mpd's currentsong returns not
        # "title" key
        config = {
            'currentsong.return_value':
                {'file': '1-silence.mp3', 'artist': 'Prince'},
            'status.return_value':
                {'state': 'play', 'time': '100:300', 'remaining_time': '0:15'},
            'sticker_list.return_value': {'dj': '', 'player_id': 1}
        }
        mpd_client.return_value.configure_mock(**config)
        result = mpc.currently_playing()

        # then we get the expected dict with "title" set to None
        expected = {
            'artist': 'Prince',
            'title': None,
            'artist_image': '/artist/Prince/image',
            'total_time': 300,
            'remaining_time': 200,
            'station_id': self.station.pk,
            'dj': ''
        }
        self.assertEqual(result, expected)

    def test_add_entry_to_playlist(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # given the song Entry
        entry = Entry.objects.create(
            queue=self.player.queue,
            station=self.station,
            song=UploadedFile(BytesIO(), 'BS.mp3'),
            title='Break Stuff',
            artist='Limp Bizkit',
            filetype='mp3'
        )

        # when we call .entry_file_to_playlist()
        with patch('teamplayer.lib.mpc.MPC.wait_for_song') as mock_wait:
            mock_wait.return_value = True
            filename = mpc.add_entry_to_playlist(entry)

        # then the file is added to the mpd playlist
        self.assertNotEqual(filename, None)
        expected = call().add(filename)
        self.assertTrue(expected in mpd_client.mock_calls)
        expected = call().play()
        self.assertTrue(expected in mpd_client.mock_calls)

    def test_add_entry_to_playlist_but_file_never_made_it(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # given the song Entry
        entry = Entry.objects.create(
            queue=self.player.queue,
            station=self.station,
            song=UploadedFile(BytesIO(), 'BS.mp3'),
            title='Break Stuff',
            artist='Limp Bizkit',
            filetype='mp3'
        )

        # when we call .entry_file_to_playlist() but the doesn't make it
        with patch('teamplayer.lib.mpc.MPC.wait_for_song') as mock_wait:
            mock_wait.return_value = False
            filename = mpc.add_entry_to_playlist(entry)

        # then None is returned
        self.assertEqual(filename, None)

        # and nothing is added to the playlist
        expected = call().add(filename)
        self.assertTrue(expected not in mpd_client.mock_calls)
        expected = call().play()
        self.assertTrue(expected not in mpd_client.mock_calls)

    def test_add_entry_to_playlist_but_file_disappears(self, mpd_client):
        # this happened.  can't explain why, but there's a test...
        # given the mpc instance
        mpc = self.mpc

        # given the song Entry
        entry = Entry.objects.create(
            queue=self.player.queue,
            station=self.station,
            song=UploadedFile(BytesIO(), 'BS.mp3'),
            title='Break Stuff',
            artist='Limp Bizkit',
            filetype='mp3'
        )

        # when we call .entry_file_to_playlist() but the doesn't make it
        with patch('teamplayer.lib.mpc.MPC.wait_for_song') as mock_wait:
            mock_wait.return_value = False
            # and attempting to remove it raises FileNotFoundError
            with patch('teamplayer.lib.mpc.os.unlink') as mock_unlink:
                mock_unlink.side_effect = FileNotFoundError  # NOQA
                filename = mpc.add_entry_to_playlist(entry)

        # then None is returned
        self.assertEqual(filename, None)

    def test_connect(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we use the connect() context manager
        with mpc.connect():
            pass

        # then it connects and disconnects
        expected = [
            call(),
            call().connect(mpc.address, mpc.port),
            call().disconnect()
        ]
        self.assertEqual(mpd_client.mock_calls, expected)

    def test_fail_exit_when_not_connected(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we use the connect() context manager and a mpd.ConnectionError
        # occurs when we exit
        mpd_client.return_value.disconnect.side_effect = ConnectionError
        try:
            with mpc.connect():
                pass
        except ConnectionError:
            self.fail('ConnectionError was not caught')
        # Then it should not error
        self.assertTrue(True)

    def test_call(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call .call()
        mpc.call('idle', 'playlist')

        # then it connects to the mpd, calls our function and disconnects
        expected = [
            call(),
            call().connect(mpc.address, mpc.port),
            call().idle('playlist'),
            call().disconnect()
        ]
        self.assertEqual(mpd_client.mock_calls, expected)

    def test_wait_for_song_True(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call wait_for_song and the song shows up
        mpd_client.return_value.listall.return_value = [{'file': 'song.mp3'}]
        result = mpc.wait_for_song('song.mp3')

        # then it return True
        self.assertTrue(result)

    def test_wait_for_song_False(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call wait_for_song and the song never shows up
        mpd_client.return_value.listall.return_value = []
        result = mpc.wait_for_song('song.mp3')

        # then it return False
        self.assertFalse(result)

    def test_purge_queue_dir(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call .purge_queue_dir()
        mpd_client.configure_mock(**{
            'return_value.listall.return_value':
                [{'file': 'foo.mp3'}, {'file': 'bar.flac'}],
            'return_value.playlist.return_value':
                ['file: baz.mp4', 'file: bar.flac']
        })
        with patch('teamplayer.lib.mpc.os.remove') as mock_remove:
            mpc.purge_queue_dir()

        # then it removes foo.mp3 because it's in listall but not on the
        # playlist
        expected = [call(os.path.join(mpc.queue_dir, 'foo.mp3'))]
        self.assertEqual(mock_remove.mock_calls, expected)

    def test_get_last_artist(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # given the playlist list
        playlist = ['file: %s' % self.filename]

        # when we call get_last_artist()
        artist = mpc.get_last_artist(playlist)

        # then we get the expected artist
        self.assertEqual(artist, 'TeamPlayer')

    def test_idle_or_wait(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call idle_or_wait(10) on a song with 1 sec to go
        def mock_idle(_):
            time.sleep(1)

        mpd_client.return_value.idle.side_effect = mock_idle
        start = time.time()
        mpc.idle_or_wait(10)
        elapsed = time.time() - start

        # then it only waits for 2 seconds
        self.assertAlmostEqual(elapsed, 1, 2)

    def test_idle_or_wait_timeout(self, mpd_client):
        # given the mpc instance
        mpc = self.mpc

        # when we call idle_or_wait(1) on a song with 10 secs to go
        def mock_idle(_):
            time.sleep(10)

        mpd_client.return_value.idle.side_effect = mock_idle
        start = time.time()
        mpc.idle_or_wait(1)
        elapsed = time.time() - start

        # then it only waits for 2 seconds
        self.assertAlmostEqual(elapsed, 1, 2)

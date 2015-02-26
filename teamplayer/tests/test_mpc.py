"""Tests for the MPC client"""
import os
from unittest.mock import call, patch

from django.test import TestCase
from mpd import ConnectionError, MPDClient

from teamplayer.lib.mpc import MPC
from teamplayer.models import Player, Station


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

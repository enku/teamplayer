from django.test import TestCase

from mock import patch

from teamplayer import scrobbler
from teamplayer.lib import songs


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

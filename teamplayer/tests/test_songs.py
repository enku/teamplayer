from django.test import TestCase

from mock import patch

from teamplayer import scrobbler
from teamplayer.lib import songs


class ScrobbleSongError(TestCase):
    """
    Demonstrate the ProtocolError thrown during scrobble_song
    """
    @patch('teamplayer.scrobbler.submit', side_effect=scrobbler.ProtocolError)
    def test_error(self, _):
        # given the "song"
        song = {
            'artist': 'Prince',
            'title': 'Purple Rain',
            'total_time': 500,
        }

        # when we scrobble it and the scrobbler raises an error
        status = songs.scrobble_song(song)

        # Then the exception is not propogated and we just get a False return
        self.assertEqual(status, False)

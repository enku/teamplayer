from django.test import SimpleTestCase

from tp_library.models import SongFile


class SongFileTest(SimpleTestCase):
    def test_not_exists(self):
        """Demonstrate the exists() for nonexistant files method."""
        # given the song pointing to a non-existant file
        song = SongFile(
            filename='/this/path/does/not/exist',
            artist='DJ Ango',
            title='No Such File',
            length=300,
        )

        # when we call exist() on the SongFile
        exists = song.exists()

        # then we get false
        self.assertFalse(exists)

    def test__not_exists(self):
        """Demonstrate the exists() for existant files method."""
        # given the song pointing to a non-existant file
        song = SongFile(
            filename='/dev/null',  # yeah, i know this is bad
            artist='DJ Ango',
            title='No Such File',
            length=300,
        )

        # when we call exist() on the SongFile
        exists = song.exists()

        # then we get true
        self.assertTrue(exists)

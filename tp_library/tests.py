import json
import logging
import os
import shutil
import tempfile
from unittest.mock import patch

from django.core import management
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.test import TestCase
from mutagen import File

from teamplayer.models import Entry, Player, Station
from tp_library.models import SongFile

__dir__ = os.path.dirname(__file__)
SILENCE = os.path.join(__dir__, '..', 'teamplayer', 'tests', 'data',
                       'silence.mp3')
DATURA = os.path.join(__dir__, '..', 'teamplayer', 'tests', 'data',
                      'd\u0101tura.mp3')  # dātura.mp3


class SongFileTest(TestCase):
    def setUp(self):
        self.dj_ango = Player.dj_ango()
        self.station = Station.main_station()

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

    def test_exists(self):
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

    def test_artist_is_unknown(self):
        # given the songfile with artist='unknown'
        metadata = File(SILENCE, easy=True)
        metadata['artist'] = 'unknown'
        contributor = self.dj_ango
        station_id = self.station.pk

        # then it raises ValidationError
        with self.assertRaises(ValidationError):
            # when we call metadata_get_or_create()
            song, created = SongFile.metadata_get_or_create(
                '/dev/null', metadata, contributor, station_id)


class AddToQueueTest(TestCase):
    def setUp(self):
        self.song = SongFile.objects.create(
            filename=SILENCE,
            artist='TeamPlayer',
            title='Station Break',
            album='You Complete Me',
            genre='Unknown',
            length=300,
            filesize=3000,
            station_id=1,
            mimetype='audio/mp3',
            added_by=Player.dj_ango(),
        )
        self.url = reverse('tp_library.views.add_to_queue')
        self.player = Player.objects.create_player('test', password='test')

    @patch('tp_library.views.IPCHandler.send_message')
    def test_add_to_queue(self, mock):
        """add_to_queue view"""
        self.client.login(username='test', password='test')
        response = self.client.post(self.url, {'song_id': self.song.pk})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertTrue('error' not in data)

        # look in the user's queue, we should have that song
        song = Entry.objects.filter(queue=self.player.queue)
        self.assertEqual(song.count(), 1)


class AddSongWithUTF8Filename(TestCase):
    # The reason why I wrote this test was: It was failing in deployment.  When
    # I tried to add a song with filename Dātura, it gave the error:
    # "UnicodeEncodeError: 'ascii' codec can't encode character '\u0101' in
    # position 63: ordinal not in range(128)".  I could not duplicate the error
    # in this test.  When I added a print(type(songfile.name)) in the deployed
    # version it suddenly started to work... wtf.  If it happens again I'll
    # have to come back to this and revise the test.
    def setUp(self):
        self.datura = SongFile.objects.create(
            filename=DATURA,
            artist='Tori Amos',
            title='D\u0101tura',
            album='To Venus and Back',
            genre='Unknown',
            length=300,
            filesize=3000,
            station_id=1,
            mimetype='audio/mp3',
            added_by=Player.dj_ango(),
        )
        self.url = reverse('tp_library.views.add_to_queue')
        self.player = Player.objects.create_player('test', password='test')

    @patch('tp_library.views.IPCHandler.send_message')
    def test_add_utf8_filename(self, mock):
        self.client.login(username='test', password='test')
        response = self.client.post(self.url, {'song_id': self.datura.pk})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertTrue('error' not in data)

        # look in the user's queue, we should have that song
        song = Entry.objects.filter(queue=self.player.queue)
        self.assertEqual(song.count(), 1)


class TpLibraryWalkTestCase(TestCase):
    """Tests for the tplibrarywalk management command"""
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.logger = logging.getLogger('tplibrarywalk')
        self.orig_loglevel = self.logger.getEffectiveLevel()
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        shutil.rmtree(self.directory)
        self.directory = None
        self.logger.setLevel(self.orig_loglevel)

    def test_bad_flac_file(self):
        """Bad FLAC file"""
        # Given the bad flac file
        filename = 'bad.flac'
        filename = os.path.join(self.directory, filename)
        open(filename, 'w').write('This is not a good FLAC file')

        # When we run tplibrarywalk on the directory
        management.call_command('tplibrarywalk', self.directory)

        # Then it succeeds, but we just don't get any files
        self.assertEqual(SongFile.objects.all().count(), 0)

    def test_unencodable_filename(self):
        filename = 'Kass\udce9 Mady Diabat\udce9 - Ko Kuma Magni.mp3'
        filename = os.path.join(self.directory, filename)

        # encoding this as utf-8 causes the following error:
        # UnicodeEncodeError: 'utf-8' codec can't encode character '\udce9' in
        # position xx: surrogates not allowed

        # This is because the filename is actually latin-1, encoded but
        # Python(3) decodes it as UTF-8, but can't re-encode it.
        shutil.copy(DATURA, filename)

        # When we call the management command on it
        management.call_command('tplibrarywalk', self.directory)

        # Then it succeeds, but we just don't get any files
        self.assertEqual(SongFile.objects.all().count(), 0)

    def test_unencodable_filename_rename(self):
        filename = 'Kass\udce9 Mady Diabat\udce9 - Ko Kuma Magni.mp3'
        filename = os.path.join(self.directory, filename)

        # This is because the filename is actually latin-1, encoded but
        # Python(3) decodes it as UTF-8, but can't re-encode it.
        shutil.copy(DATURA, filename)

        # When we call the management command on it with --rename
        management.call_command(
            'tplibrarywalk', self.directory, rename=True)

        # Then it succeeds and the file is renamed
        self.assertEqual(SongFile.objects.all().count(), 1)

        songfile = SongFile.objects.all()[0]
        expected = os.path.join(
            self.directory, 'Kass\u00e9 Mady Diabat\u00e9 - Ko Kuma Magni.mp3')
        self.assertEqual(songfile.filename, expected)

import json
import os

from mock import patch

from teamplayer.models import Entry, Player
from tp_library.models import SongFile

from django.core.urlresolvers import reverse
from django.test import TestCase

__dir__ = os.path.dirname(__file__)
SILENCE = os.path.join(__dir__, '..', 'teamplayer', 'tests', 'data',
                       'silence.mp3')
DATURA = os.path.join(__dir__, '..', 'teamplayer', 'tests', 'data',
                      'd\u0101tura.mp3')  # dātura.mp3


class SongFileTest(TestCase):
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

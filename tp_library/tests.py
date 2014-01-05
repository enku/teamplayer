import json
import os

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import SimpleTestCase

from teamplayer.lib import users
from teamplayer.models import Entry
from tp_library.models import SongFile
from mock import patch

__dir__ = os.path.dirname(__file__)
SILENCE = os.path.join(__dir__, '..', 'teamplayer', 'tests', 'data',
                       'silence.mp3')


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


class AddToQueueTest(SimpleTestCase):
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
            added_by=User.objects.get(username='DJ Ango'),
        )
        self.url = reverse('tp_library.views.add_to_queue')
        self.user = users.create_user(username='test', password='test')
        self.player = self.user.player

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

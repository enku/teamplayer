"""Unit tests for the TeamPlayer Django app"""
import os
from tempfile import TemporaryDirectory

import django.contrib.auth.models
import django.core.files.uploadedfile
import django.core.urlresolvers
import django.test
import mock

from teamplayer.lib import users
from teamplayer.models import Entry, Station
from teamplayer.tests import utils
from tp_library.models import SongFile

SILENCE = utils.SILENCE
METALLICA_SIMILAR_TXT = utils.METALLICA_SIMILAR_TXT
PRINCE_SIMILAR_TXT = utils.PRINCE_SIMILAR_TXT
SpinDoctor = utils.SpinDoctor
TestCase = django.test.TestCase
UploadedFile = django.core.files.uploadedfile.UploadedFile
User = django.contrib.auth.models.User

patch = mock.patch
reverse = django.core.urlresolvers.reverse


class UserQueue(TestCase):

    def setUp(self):
        self.user_data = {
            'username': 'br',
            'password': 'blah blah',
        }

        self.user = users.create_user(**self.user_data)

    @patch('teamplayer.views.IPCHandler.send_message')
    def test_can_login(self, mock):
        """Assert that the user can login"""

        redirect_url = reverse('teamplayer.views.home')
        url = '/accounts/login/?next=%s' % redirect_url
        response = self.client.post(url, self.user_data)
        self.assertEqual(response.status_code, 302)

    @patch('teamplayer.views.IPCHandler.send_message')
    def test_add_entries(self, mock):
        """Test that user can add entries"""
        song = open(SILENCE, 'rb')
        view = reverse('teamplayer.views.add_to_queue')

        # first, verify user has an empty queue
        self.assertEqual(self.user.player.queue.entry_set.count(), 0)
        # log in as the user
        self.client.login(username=self.user_data['username'],
                          password=self.user_data['password'])
        self.client.post(view, {'song': song}, follow=True)
        self.assertEqual(self.user.player.queue.entry_set.count(), 1)

    @patch('teamplayer.views.IPCHandler.send_message')
    def test_delete_entries(self, mock):
        """
        Test that user can delete entries
        """
        # first add the entry
        self.test_add_entries()
        song_id = self.user.player.queue.entry_set.all()[0].pk
        view = reverse('teamplayer.views.show_entry', args=(song_id,))
        self.client.delete(view)
        self.assertEqual(self.user.player.queue.entry_set.count(), 0)


class Queue(TestCase):

    """
    Test various operations on the Queue model
    """
    def setUp(self):
        self.station = Station.main_station()
        self.user = users.create_user('test', 'test')
        self.player = self.user.player

        # add some songs
        for _ in range(5):
            Entry.objects.create(
                song=SILENCE,
                queue=self.player.queue,
                station=self.station,
            )

    def test_reorder(self):
        order = [x['id'] for x in self.player.queue.entry_set.values()]
        new_order = list(reversed(order))
        result = self.player.queue.reorder(new_order)
        self.assertEqual(new_order, [x['id'] for x in result])


class QueueAutoFill(TestCase):
    """
    Demonstrate the auto_fill() method.
    """
    def setUp(self):
        self.dj_ango = User.dj_ango()
        self.station = Station.main_station()

        # create a SongFile
        self.songfile = SongFile.objects.create(
            filename=SILENCE,
            filesize=500,
            station_id=self.station.pk,
            added_by=self.dj_ango,
            length=301,
        )

    def test_auto_fill(self):
        queue = self.dj_ango.player.queue

        # when we filter songs < 5 minutes
        queue.auto_fill(
            max_entries=100,
            station=self.station,
            qs_filter={'length__lt': 300}
        )

        # then we don't get our 301-second songfile
        self.assertEqual(queue.entry_set.count(), 0)

    def test_multiple_files(self):
        """We can have multiple files and get back as many as we ask for"""
        queue = self.dj_ango.player.queue
        with TemporaryDirectory() as tempdir:
            silence = open(SILENCE, 'rb').read()
            filesize = len(silence)
            for i in range(10):
                filename = '{0}.mp3'.format(i)
                fullpath = os.path.join(tempdir, filename)
                open(fullpath, 'wb').write(silence)
                SongFile.objects.create(
                    filename=fullpath,
                    artist='DJ Ango',
                    title='Song {0}'.format(i),
                    album='Redundant',
                    filesize=filesize,
                    station_id=self.station.pk,
                    added_by=self.dj_ango,
                    length=301,
                )
            self.assertEqual(SongFile.objects.count(), 11)
            queue.auto_fill(
                max_entries=5,
                station=self.station,
                qs_filter={'length__lt': 600}
            )
            self.assertEqual(queue.entry_set.count(), 5)


class StationTest(TestCase):

    """Demonstrate the Station model"""
    def setUp(self):
        self.user = users.create_user('test', 'test')
        self.player = self.user.player

    def test_create_station(self):
        """Demonstrate the create_station method."""
        station = Station.create_station('My Station', self.user)
        self.assertTrue(isinstance(station, Station))

    def test_get_songs(self):
        """Test that get_songs shows files on that station"""
        # given the stations
        station1 = Station.create_station('station1', self.user)
        user2 = users.create_user('test2', 'test2')
        station2 = Station.create_station('station2', user2)

        # with a song in each station
        song1 = Entry.objects.create(
            song=SILENCE,
            queue=self.player.queue,
            station=station1,
        )
        Entry.objects.create(
            song=SILENCE,
            queue=self.player.queue,
            station=station2,
        )

        # when we call .get_songs() on a station
        song_qs = station1.get_songs()

        # then we get only the song in that station
        self.assertEqual(list(song_qs), [song1])

    def test_get_stations(self):
        """Demonstrate the get_stations() method."""
        # given the stations
        user2 = users.create_user('test2', 'test2')
        station2 = Station.create_station('station2', user2)
        station1 = Station.create_station('station1', self.user)

        # and the "built-in" station
        station0 = Station.main_station()

        # when we call get_stations()
        stations = Station.get_stations()

        # then we get the stations (sorted by id)
        self.assertEqual(
            list(stations),
            [station0, station2, station1]
        )

    def test_add_song_with_station(self):
        """Demonstrate Queue.add_song() with a station."""
        # given the station
        station = Station.create_station('station', self.user)

        # when i call .add_song() on a queue
        queue = self.user.player.queue
        entry = queue.add_song(
            UploadedFile(open(SILENCE, 'rb')), station=station)

        # the song is created in the user's queue and with the station
        self.assertEqual(entry.queue, self.user.player.queue)
        self.assertEqual(entry.station, station)

    def test_from_user(self):
        """Demonstrate the from_user() classmethod."""
        # given the station
        station = Station.create_station('station', self.user)

        # when we call the from_user classmethod
        result = Station.from_user(self.user)

        # then we get the station.
        self.assertEqual(result, station)

    def test_from_user_returns_none(self):
        """Demonstrate that from user returns None if a user has none."""
        self.assertEqual(Station.from_user(self.user), None)

    @patch('teamplayer.views.MPC')
    def test_cannot_name_teamplayer_view(self, MockMPC):
        station = Station.create_station('My Station', self.user)
        view = 'teamplayer.views.edit_station'
        post = {'station_id': station.pk,
                'action': 'rename',
                'name': 'TeamPlayer'}

        self.client.login(username='test', password='test')
        response = self.client.post(
            reverse(view),
            post,
            follow=True,
            HTTP_REFERRER=reverse('teamplayer.views.show_stations'))

        self.assertContains(response, "is an invalid name")


class QueueMasterTestCase(TestCase):

    """Test case to test that queues spinning does as it should"""
    def setUp(self):
        # need to create some users
        self.user1 = users.create_user(username='user1', password='pass')
        self.user1.player.dj_name = 'user1'
        self.user1.player.save()
        self.user2 = users.create_user(username='user2', password='pass')
        self.user2.player.dj_name = 'user2'
        self.user2.player.save()
        self.user3 = users.create_user(username='user3', password='pass')
        self.user3.player.dj_name = 'user3'
        self.user3.player.save()
        self.spin = SpinDoctor()

    def test_plays_users_song(self):
        self.assertEqual(self.spin.current_song, self.spin.silence)
        self.spin.create_song_for(self.user1, artist='Prince',
                                  title='Purple Rain')
        current = self.spin.next()
        self.assertEqual(self.spin.current_user, self.user1)
        self.assertEqual(current[1], 'Prince')
        self.assertEqual(current[2], 'Purple Rain')

    @patch('teamplayer.lib.songs.urlopen')
    def test_round_robin(self, mock_urlopen):
        self.spin.create_song_for(self.user1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.user2, artist='Metallica',
                                  title='One')
        self.spin.create_song_for(self.user3, artist='Interpol',
                                  title='Take You On a Cruise')

        self.spin.next()
        first_user = self.spin.current_user
        self.spin.next()
        second_user = self.spin.current_user
        self.spin.next()
        third_user = self.spin.current_user

        self.assertNotEqual(first_user, second_user)
        self.assertNotEqual(second_user, third_user)

    def test_only_one_user(self):
        """if only one user has songs, play his next song"""
        self.spin.create_song_for(self.user1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.user1, artist='Metallica',
                                  title='One')

        song1 = self.spin.next()
        self.assertEqual(self.spin.current_user, self.user1)
        song2 = self.spin.next()
        self.assertEqual(self.spin.current_user, self.user1)
        self.assertNotEqual(song1, song2)

    def test_remove_from_queue(self):
        """Test that when a user's songs get played they're removed from
        the queue
        This doesn't really test the spin process specifically, as this is
        using the "mocked" spin class, but the code is nearly identical, so
        it's quasi-testing the behaviour
        """
        self.spin.create_song_for(self.user1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.user1, artist='Metallica',
                                  title='One')

        self.assertEqual(self.user1.player.queue.entry_set.count(),
                         2)
        self.spin.next()
        self.assertEqual(self.user1.player.queue.entry_set.count(),
                         1)
        self.spin.next()
        self.assertEqual(self.user1.player.queue.entry_set.count(),
                         0)

    @patch('teamplayer.lib.songs.urlopen')
    def test_auto_mode(self, mock_urlopen):
        def my_urlopen(url):
            if 'Prince' in url:
                return open(PRINCE_SIMILAR_TXT, 'rb')
            if 'Metallica' in url:
                return open(METALLICA_SIMILAR_TXT, 'rb')
            return open(os.devnull, 'rb')

        mock_urlopen.side_effect = my_urlopen

        self.spin.create_song_for(self.user1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.user1, artist='Metallica',
                                  title='One')
        self.spin.create_song_for(self.user1, artist='The Time',
                                  title='Jungle Love')
        player = self.user1.player
        player.auto_mode = True
        player.save()

        current = self.spin.next()  # should play "Purple Rain"
        self.assertEqual(current[1], 'Prince')

        current = self.spin.next(
        )  # should preempt Metallica and play The Time
        self.assertEqual(current[1], 'The Time')

        current = self.spin.next(
        )  # should preempt Metallica and play The Time
        self.assertEqual(current[1], 'Metallica')

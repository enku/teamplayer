"""Unit tests for the TeamPlayer Django app"""
import datetime
import json
import os
import pickle
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest import mock

import django.contrib.auth.models
import django.core.files.uploadedfile
import django.core.urlresolvers
import django.test
from django.core.files import File

from teamplayer.conf import settings
from teamplayer.lib import songs
from teamplayer.models import Entry, Mood, Player, Queue, Station
from teamplayer.tests import utils
from tp_library.models import SongFile

SILENCE = utils.SILENCE
SpinDoctor = utils.SpinDoctor
TestCase = django.test.TestCase
UploadedFile = django.core.files.uploadedfile.UploadedFile

patch = mock.patch
reverse = django.core.urlresolvers.reverse


class PlayerTestCase(TestCase):
    def setUp(self):
        self.player = Player.objects.create_player('test_player',
                                                   password='test')

    def test_create_player(self):
        player = self.player
        self.assertEqual(player.username, 'test_player')
        self.assertTrue(hasattr(player, 'queue'))

        logged_in = self.client.login(username='test_player', password='test')
        self.assertTrue(logged_in)

    def test_str(self):
        # Given the player
        player = self.player

        # When we str() it
        result = str(player)

        # Then we get the username
        self.assertEqual(result, player.user.username)

    def test_toggle_auto_mode(self):
        # Given the player
        player = self.player

        # When toggle_auto_mode is called
        result = player.toggle_auto_mode()

        # Then auto mode is turned on
        self.assertTrue(result)
        self.assertTrue(player.auto_mode)

        # When toggle_auto_mode is called again
        result = player.toggle_auto_mode()

        # Then auto mode is turned off
        self.assertFalse(result)
        self.assertFalse(player.auto_mode)

    def test_player_stats_property(self):
        # Given the Player class
        # When we access the player_stats classmethod
        result = Player.player_stats()

        expected = {
            'active_queues': 1,
            'songs': 0,
            'stations': 1,
        }
        # Then we get stats
        self.assertEqual(result, expected)


class QueueViewsTestCase(TestCase):

    def setUp(self):
        self.user_data = {
            'username': 'br',
            'password': 'blah blah',
        }

        self.player = Player.objects.create_player(**self.user_data)

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
        self.assertEqual(self.player.queue.entry_set.count(), 0)
        # log in as the user
        self.client.login(username=self.user_data['username'],
                          password=self.user_data['password'])
        self.client.post(view, {'song': song}, follow=True)
        self.assertEqual(self.player.queue.entry_set.count(), 1)

    @patch('teamplayer.views.IPCHandler.send_message')
    def test_delete_entries(self, mock):
        """
        Test that user can delete entries
        """
        # first add the entry
        self.test_add_entries()
        song_id = self.player.queue.entry_set.all()[0].pk
        view = reverse('teamplayer.views.show_entry', args=(song_id,))
        self.client.delete(view)
        self.assertEqual(self.player.queue.entry_set.count(), 0)


class QueueTestCase(TestCase):

    """
    Test various operations on the Queue model
    """
    def setUp(self):
        self.station = Station.main_station()
        self.player = Player.objects.create_player('test', password='test')

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

    def test_str(self):
        """str()"""
        # Given the queue
        queue = self.player.queue

        result = str(queue)
        self.assertEqual(result, "test's Queue")

    def test_add_song_with_extension(self):
        queue = self.player.queue

        with open(SILENCE, 'rb') as fp:
            # Given the song_file with no extension
            song_file = UploadedFile(fp, 'silence.mp3')

            # When we add the file to our queue
            result = queue.add_song(song_file, self.station)

            # Then we get an entry whos filename has the same extension
            self.assertTrue(isinstance(result, Entry))
            self.assertTrue(result.song.name.endswith('.mp3'))

    def test_add_song_with_no_extension(self):
        queue = self.player.queue

        with open(SILENCE, 'rb') as fp:
            # Given the song_file with no extension
            song_file = UploadedFile(fp, 'test_no_extension')

            # When we add the file to our queue
            result = queue.add_song(song_file, self.station)

            # Then we get an entry, but the entry's file has no extension
            self.assertTrue(isinstance(result, Entry))
            self.assertFalse('.' in result.song.name)

    def test_queue_user_property(self):
        queue = self.player.queue
        user = self.player.user
        self.assertEqual(queue.user, user)

    def test_toggle_status(self):
        queue = self.player.queue
        original_status = queue.active

        queue.toggle_status()

        new_status = queue.active
        self.assertNotEqual(new_status, original_status)

    def test_auto_fill_mood(self):
        # given the set of songs in our library
        songs = (
            ('Madonna', 'True Blue'),
            ('Sleigh Bells', 'End of the Line'),
            ('The Love Language', 'Heart to Tell'),
            ('Pace is the Trick', 'Interpol'),
            ('Wander (Through the Night)', 'The B of the Bang'),
            ('Lord We Ganstas', 'Slipstick'),
            ('Grammy', 'Purity Ring'),
            ('Bullet in the Head', 'Gvcci Hvcci')
        )
        dj_ango = Player.dj_ango()
        main_station = Station.main_station()
        for song in songs:
            SongFile.objects.create(
                artist=song[0],
                title=song[1],
                filename='{0}-{1}.mp3'.format(*song),
                filesize=80000,
                album="Marduk's Mix Tape",
                genre="Unknown",
                station_id=main_station.pk,
                added_by=dj_ango,
            )

        # and the current mood
        Mood.objects.create(station=main_station, artist='Sleigh Bells')
        Mood.objects.create(station=main_station, artist='Crystal Castles')
        Mood.objects.create(station=main_station, artist='Sleigh Bells')
        Mood.objects.create(station=main_station, artist='Prince')
        Mood.objects.create(station=main_station, artist='Prince')
        Mood.objects.create(station=main_station, artist='Prince')

        # when we call Queue.auto_fill_mood()
        qs = SongFile.objects.all()
        needed = 2
        result = list(Queue.auto_fill_mood(qs, needed))

        # Then we get the expected two songs
        self.assertEqual(len(result), 2)

        # And the first song should be Sleigh Bells
        self.assertEqual(result[0].artist, 'Sleigh Bells')

        # And the second artists should be random but not the sleigh bells song
        self.assertNotEqual(result[1].artist, 'Sleigh Bells')

    def test_auto_fill_mood_recurses(self):
        # given the set of songs in our library
        songs = (
            ('Madonna', 'True Blue'),
            ('Sleigh Bells', 'End of the Line'),
            ('The Love Language', 'Heart to Tell'),
            ('Pace is the Trick', 'Interpol'),
            ('Wander (Through the Night)', 'The B of the Bang'),
            ('Lord We Ganstas', 'Slipstick'),
            ('Grammy', 'Purity Ring'),
            ('Bullet in the Head', 'Gvcci Hvcci')
        )
        dj_ango = Player.dj_ango()
        main_station = Station.main_station()
        for song in songs:
            SongFile.objects.create(
                artist=song[0],
                title=song[1],
                filename='{0}-{1}.mp3'.format(*song),
                filesize=80000,
                album="Marduk's Mix Tape",
                genre="Unknown",
                station_id=main_station.pk,
                added_by=dj_ango,
            )

        # Given the current mood
        now = datetime.datetime.now()
        one_hour_ago = now - datetime.timedelta(seconds=3600)
        Mood.objects.create(
            station=main_station, artist='Sleigh Bells', timestamp=now)
        Mood.objects.create(
            station=main_station, artist='Prince', timestamp=one_hour_ago)

        # when we call Queue.auto_fill_mood()
        qs = SongFile.objects.all()
        needed = 2
        result = list(Queue.auto_fill_mood(qs, needed, seconds=900))

        # Then we get the expected two songs
        self.assertEqual(len(result), 2)

        # And the first song should be Sleigh Bells
        self.assertEqual(result[0].artist, 'Sleigh Bells')

        # And the second should be Prince because he's not the current mood but
        # was on the last hour
        self.assertNotEqual(result[1].artist, 'Prince')

    def test_auto_fill_mood_not_recurses(self):
        # given the set of songs in our library
        songs = (
            ('Madonna', 'True Blue'),
            ('Sleigh Bells', 'End of the Line'),
            ('The Love Language', 'Heart to Tell'),
            ('Pace is the Trick', 'Interpol'),
            ('Wander (Through the Night)', 'The B of the Bang'),
            ('Lord We Ganstas', 'Slipstick'),
            ('Grammy', 'Purity Ring'),
            ('Bullet in the Head', 'Gvcci Hvcci')
        )
        dj_ango = Player.dj_ango()
        main_station = Station.main_station()
        for song in songs:
            SongFile.objects.create(
                artist=song[0],
                title=song[1],
                filename='{0}-{1}.mp3'.format(*song),
                filesize=80000,
                album="Marduk's Mix Tape",
                genre="Unknown",
                station_id=main_station.pk,
                added_by=dj_ango,
            )

        # given no mood
        assert not Mood.objects.all().exists()

        # when we call Queue.auto_fill_mood()
        qs = SongFile.objects.all()
        needed = 2
        result = list(Queue.auto_fill_mood(qs, needed, seconds=900))

        # Then we get the expected two songs even if there was no mood
        self.assertEqual(len(result), 2)

    def test_randomize_no_repeats(self):
        Entry.objects.all().delete()
        # given the queue
        queue = self.player.queue

        # given the station
        station = Station.main_station()

        # given the songs in the queue for that station
        songs = (
            ('Madonna', 'True Blue'),
            ('Sleigh Bells', 'End of the Line'),
            ('The Love Language', 'Heart to Tell'),
            ('Pace is the Trick', 'Interpol'),
            ('Wander (Through the Night)', 'The B of the Bang'),
            ('Lord We Ganstas', 'Slipstick'),
            ('Grammy', 'Purity Ring'),
            ('Bullet in the Head', 'Gvcci Hvcci')
        )
        for artist, title in songs:
            Entry.objects.create(
                queue=queue,
                station=station,
                song=UploadedFile(BytesIO(), '%s.mp3' % title),
                title=title,
                artist=artist,
                filetype='mp3'
            )

        # when we call randomize() on the queue for that station
        queue.randomize(station)

        # then the entries get a unique random order
        entries = Entry.objects.filter(station=station, queue=queue)
        places = entries.values_list('place', flat=True)
        places = list(places)
        places.sort()
        self.assertEqual(places, list(range(len(songs))))


class QueueAutoFill(TestCase):
    """
    Demonstrate the auto_fill() method.
    """
    def setUp(self):
        self.dj_ango = Player.dj_ango()
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
        queue = self.dj_ango.queue

        # when we filter songs < 5 minutes
        queue.auto_fill(
            max_entries=100,
            station=self.station,
            qs_filter={'length__lt': 300}
        )

        # then we don't get our 301-second songfile
        self.assertEqual(queue.entry_set.count(), 0)

    def test_auto_fill_contiguous(self):
        # given the queue
        queue = self.dj_ango.queue

        # given the setting to use contiguous
        with patch.object(settings, 'AUTOFILL_STRATEGY', 'contiguous'):
            # when we call auto_fill()
            with patch('teamplayer.models.Queue.auto_fill_contiguous') \
                    as auto_fill_contiguous:
                auto_fill_contiguous.return_value = [self.songfile] * 10
                queue.auto_fill(10)

        # then it calls auto_fill_contiguous
        self.assertTrue(auto_fill_contiguous.called)

        # and the requested songs get added
        self.assertEqual(queue.entry_set.count(), 10)

    def test_auto_fill_mood(self):
        # given the queue
        queue = self.dj_ango.queue

        # given the setting to use mood
        with patch.object(settings, 'AUTOFILL_STRATEGY', 'mood'):
            # when we call auto_fill()
            with patch('teamplayer.models.Queue.auto_fill_mood') \
                    as auto_fill_mood:
                auto_fill_mood.return_value = [self.songfile] * 10
                queue.auto_fill(10)

        # then it calls auto_fill_mood
        self.assertTrue(auto_fill_mood.called)

        # and the requested songs get added
        self.assertEqual(queue.entry_set.count(), 10)

    def test_auto_fill_random(self):
        # given the queue
        queue = self.dj_ango.queue

        # given the setting to use random
        with patch.object(settings, 'AUTOFILL_STRATEGY', 'random'):
            # when we call auto_fill()
            with patch('teamplayer.models.Queue.auto_fill_random') \
                    as auto_fill_random:
                auto_fill_random.return_value = [self.songfile] * 10
                queue.auto_fill(10)

        # then it calls auto_fill_random
        self.assertTrue(auto_fill_random.called)

        # and the requested songs get added
        self.assertEqual(queue.entry_set.count(), 10)

    def test_auto_fill_already_has_enough_entries(self):
        # given the queue that already has 10 entries
        queue = self.dj_ango.queue
        fp = File(open(self.songfile.filename, 'rb'))
        for i in range(10):
            queue.add_song(fp, self.station)
        self.assertEqual(queue.entry_set.count(), 10)

        # given the setting to use random
        with patch.object(settings, 'AUTOFILL_STRATEGY', 'random'):
            # when we call auto_fill()
            with patch('teamplayer.models.Queue.auto_fill_random') \
                    as auto_fill_random:
                auto_fill_random.return_value = [self.songfile] * 10
                queue.auto_fill(10)

        # then it doesn't even bother to call auto_fill_random
        self.assertTrue(not auto_fill_random.called)

        # and no new songs get added
        self.assertEqual(queue.entry_set.count(), 10)

    def test_auto_fill_user_station_with_hashtag(self):
        # given the player
        player = Player.objects.create_player('test', password='***')

        # given the player's station with a hashtag in the name
        station = Station.objects.create(creator=player, name='#electronic')

        # when we call auto_fill() with the station
        with patch('teamplayer.models.Queue.auto_fill_from_tags') \
                as auto_fill_from_tags:
            auto_fill_from_tags.return_value = [self.songfile] * 10
            player.queue.auto_fill(10, station=station)

        # then it calls auto_fill_from_tags()
        args, kwargs = auto_fill_from_tags.call_args
        self.assertEqual(args[1:], (10, station))

        # and addes entries to the queue
        self.assertEqual(player.queue.entry_set.count(), 10)

    def test_auto_fill_user_station_without_hashtag(self):
        # given the player
        player = Player.objects.create_player('test', password='***')

        # given the player's station without a hashtag in the name
        station = Station.objects.create(creator=player, name='my station')

        # when we call auto_fill() with the station
        with patch('teamplayer.models.Queue.auto_fill_from_tags') \
                as auto_fill_from_tags:
            auto_fill_from_tags.return_value = [self.songfile] * 10
            player.queue.auto_fill(10, station=station)

        # then it does not call auto_fill_from_tags()
        self.assertEqual(auto_fill_from_tags.call_count, 0)

        # and nothing is added to the queue
        self.assertEqual(player.queue.entry_set.count(), 0)

    def test_multiple_files(self):
        """We can have multiple files and get back as many as we ask for"""
        queue = self.dj_ango.queue
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

    def test_auto_fill_from_tags(self):
        # given the (mock) queryset
        queryset = mock.MagicMock(name='queryset')
        queryset.count = mock.Mock(return_value=90)
        queryset.filter = mock.MagicMock(return_value=queryset)

        # given the player
        player = Player.objects.create_player('test_player', password='test')

        # given the station with a tag in the name
        station = Station.objects.create(creator=player, name='#electronic')

        # when we call auto_fill_from_tags()
        with patch('teamplayer.models.lib.songs.pylast.Tag') as Tag:
            with utils.getdata('electronic_tags.pickle', 'rb') as fp:
                tags = pickle.load(fp)
            Tag().get_top_artists.return_value = tags
            Tag.reset_mock()

            result = Queue.auto_fill_from_tags(queryset, 3, station)

        # then the queryset is filtered on the artists from the tags
        artists = songs.artists_from_tags(['electronic'])
        queryset.filter.assert_called_with(artist__in=artists)

        # and 3 items are returned
        self.assertEqual(len(result), 3)


class StationManagerTest(TestCase):
    def setUp(self):
        self.player = Player.objects.create_player('test', password='***')

    def test_create_station(self):
        # given the player
        player = self.player

        # when we call Station.objects.create_station()
        station = Station.objects.create_station(creator=player,
                                                 name='test station')

        # then we get a station with the player as creator
        self.assertEqual(station.creator, player)
        self.assertEqual(station.name, 'test station')

    def test_create_station_with_songs(self):
        # given the player
        player = self.player

        # given the songs in the library
        song_data = (
            ('Madonna', 'True Blue'),
            ('Sleigh Bells', 'End of the Line'),
            ('The Love Language', 'Heart to Tell'),
            ('Pace is the Trick', 'Interpol'),
            ('Wander (Through the Night)', 'The B of the Bang'),
            ('Lord We Ganstas', 'Slipstick'),
            ('Grammy', 'Purity Ring'),
            ('Bullet in the Head', 'Gvcci Hvcci')
        )
        main_station = Station.main_station()
        songs = []
        with TemporaryDirectory() as tempdir:
            silence = open(SILENCE, 'rb').read()
            for data in song_data:
                filename = os.path.join(tempdir, '{0}-{1}.mp3'.format(*data))
                open(filename, 'wb').write(silence)
                song = SongFile.objects.create(
                    artist=data[0],
                    title=data[1],
                    filename=filename,
                    filesize=80000,
                    album="Marduk's Mix Tape",
                    genre="Unknown",
                    station_id=main_station.pk,
                    added_by=player,
                )
                songs.append(song)

            # when we call Station.objects.create_station() with those songs
            station = Station.objects.create_station(creator=player,
                                                     name='My Station',
                                                     songs=songs)

            # then the station is created and the song entries added
            self.assertEqual(station.entries.count(), len(songs))


class StationTest(TestCase):

    """Demonstrate the Station model"""
    def setUp(self):
        self.player = Player.objects.create_player('test', password='test')

    def test_create_station(self):
        """Demonstrate the create_station method."""
        station = Station.create_station('My Station', self.player)
        self.assertTrue(isinstance(station, Station))

    def test_get_songs(self):
        """Test that get_songs shows files on that station"""
        # given the stations
        station1 = Station.create_station('station1', self.player)
        player2 = Player.objects.create_player('test2', password='test2')
        station2 = Station.create_station('station2', player2)

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
        player2 = Player.objects.create_player('test2', password='test2')
        station2 = Station.create_station('station2', player2)
        station1 = Station.create_station('station1', self.player)

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
        station = Station.create_station('station', self.player)

        # when i call .add_song() on a queue
        queue = self.player.queue
        entry = queue.add_song(
            UploadedFile(open(SILENCE, 'rb')), station=station)

        # the song is created in the user's queue and with the station
        self.assertEqual(entry.queue, self.player.queue)
        self.assertEqual(entry.station, station)

    def test_from_user(self):
        """Demonstrate the from_user() classmethod."""
        # given the station
        station = Station.create_station('station', self.player)

        # when we call the from_user classmethod
        result = Station.from_player(self.player)

        # then we get the station.
        self.assertEqual(result, station)

    def test_from_user_returns_none(self):
        """Demonstrate that from user returns None if a user has none."""
        self.assertEqual(Station.from_player(self.player), None)

    @patch('teamplayer.views.MPC')
    def test_cannot_name_teamplayer_view(self, MockMPC):
        station = Station.create_station('My Station', self.player)
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

    def test_participants(self):
        """Station.participants()"""
        # given the stations
        station = Station.create_station('My Station', self.player)
        main = Station.main_station()

        # and players
        player1 = self.player
        player2 = Player.objects.create_player('test2', password='test')

        # With a bunch of entries
        Entry.objects.create(
            artist='Elliott Smith',
            title='Happiness',
            queue=player1.queue,
            station=main
        )
        Entry.objects.create(
            artist='Prince',
            title='Purple Rain',
            queue=player1.queue,
            station=station
        )
        Entry.objects.create(
            artist='Prince',
            title='Purple Rain',
            queue=player1.queue,
            station=main
        )
        Entry.objects.create(
            artist='Elliott Smith',
            title='Happiness',
            queue=player2.queue,
            station=main
        )

        # When we call .participants() on main
        participants = main.participants()

        # Then we get both users
        self.assertEqual(participants.count(), 2)
        self.assertEqual(set(participants), set([player1, player2]))

        # And when we call .participants on station
        participants = station.participants()

        # Then we only get player1
        self.assertEqual(participants.count(), 1)
        self.assertEqual(set(participants), set([player1]))


class QueueMasterTestCase(TestCase):

    """Test case to test that queues spinning does as it should"""
    def setUp(self):
        # need to create some players
        self.player1 = Player.objects.create_player('user1',
                                                    dj_name='user1',
                                                    password='pass')
        self.player2 = Player.objects.create_player('user2',
                                                    dj_name='user2',
                                                    password='pass')
        self.player3 = Player.objects.create_player('user3',
                                                    dj_name='user3',
                                                    password='pass')
        self.spin = SpinDoctor()

    def test_plays_users_song(self):
        self.assertEqual(self.spin.current_song, self.spin.silence)
        self.spin.create_song_for(self.player1, artist='Prince',
                                  title='Purple Rain')
        current = self.spin.next()
        self.assertEqual(self.spin.current_player, self.player1)
        self.assertEqual(current[1], 'Prince')
        self.assertEqual(current[2], 'Purple Rain')

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_round_robin(self, get_similar_artists):
        self.spin.create_song_for(self.player1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.player2, artist='Metallica',
                                  title='One')
        self.spin.create_song_for(self.player3, artist='Interpol',
                                  title='Take You On a Cruise')

        self.spin.next()
        first_player = self.spin.current_player
        self.spin.next()
        second_player = self.spin.current_player
        self.spin.next()
        third_player = self.spin.current_player

        self.assertNotEqual(first_player, second_player)
        self.assertNotEqual(second_player, third_player)

    def test_only_one_user(self):
        """if only one user has songs, play his next song"""
        self.spin.create_song_for(self.player1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.player1, artist='Metallica',
                                  title='One')

        song1 = self.spin.next()
        self.assertEqual(self.spin.current_player, self.player1)
        song2 = self.spin.next()
        self.assertEqual(self.spin.current_player, self.player1)
        self.assertNotEqual(song1, song2)

    def test_remove_from_queue(self):
        """Test that when a user's songs get played they're removed from
        the queue
        This doesn't really test the spin process specifically, as this is
        using the "mocked" spin class, but the code is nearly identical, so
        it's quasi-testing the behaviour
        """
        self.spin.create_song_for(self.player1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.player1, artist='Metallica',
                                  title='One')

        self.assertEqual(self.player1.queue.entry_set.count(), 2)
        self.spin.next()
        self.assertEqual(self.player1.queue.entry_set.count(), 1)
        self.spin.next()
        self.assertEqual(self.player1.queue.entry_set.count(), 0)

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_auto_mode(self, get_similar_artists):
        def my_similar(artist):
            if artist == 'Prince':
                with utils.getdata('prince_similar.json') as fp:
                    data = json.load(fp)
            elif artist == 'Metallica':
                with utils.getdata('metallica_similar.json') as fp:
                    data = json.load(fp)
            else:
                data = []
            return data

        get_similar_artists.side_effect = my_similar

        self.spin.create_song_for(self.player1, artist='Prince',
                                  title='Purple Rain')
        self.spin.create_song_for(self.player1, artist='Metallica',
                                  title='One')
        self.spin.create_song_for(self.player1, artist='The Time',
                                  title='Jungle Love')
        player = self.player1
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


class MoodTestCase(TestCase):
    """Tests for the Mood model"""
    def test_str(self):
        # Given the Mood object
        station = Station.main_station()
        mood = Mood.objects.create(station=station, artist='Sleigh Bells')

        # then when we call str() on it
        result = str(mood)

        # then we get the expected result
        self.assertTrue('Sleigh Bells' in result)

"""Unit tests for the TeamPlayer Django app"""
import json
import os
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest import mock

import django.contrib.auth.models
import django.core.files.uploadedfile
import django.test
import django.urls
from django.utils import timezone

from teamplayer.models import (
    Entry,
    LibraryItem,
    Mood,
    Player,
    PlayLog,
    Station,
)
from teamplayer.tests import utils

SILENCE = utils.SILENCE
SpinDoctor = utils.SpinDoctor
TestCase = django.test.TestCase
UploadedFile = django.core.files.uploadedfile.UploadedFile

patch = mock.patch
reverse = django.urls.reverse


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

        redirect_url = reverse('home')
        url = f"/accounts/login/?next={redirect_url}"
        response = self.client.post(url, self.user_data)
        self.assertEqual(response.status_code, 302)

    @patch('teamplayer.views.IPCHandler.send_message')
    def test_add_entries(self, mock):
        """Test that user can add entries"""
        view = reverse('add_to_queue')

        # first, verify user has an empty queue
        self.assertEqual(self.player.queue.entry_set.count(), 0)
        # log in as the user
        self.client.login(username=self.user_data['username'],
                          password=self.user_data['password'])

        with open(SILENCE, 'rb') as song:
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
        view = reverse('show_entry', args=(song_id,))
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

    def test_added_song_has_album(self):
        # given the queue
        queue = self.player.queue

        with open(SILENCE, 'rb') as fp:
            # given the song file
            song_file = UploadedFile(fp, 'silence.mp3')

            # when we add the file to our queue
            result = queue.add_song(song_file, self.station)

            # then the Entry has the same album as the uploaded file
            self.assertEqual(result.album, 'Songs of Silence')

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
                song=UploadedFile(BytesIO(), f"{title}.mp3"),
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

        # create a LibraryItem
        self.songfile = LibraryItem.objects.create(
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

    def test_auto_fill_user_station_with_hashtag(self):
        # given the player
        player = Player.objects.create_player('test', password='***')

        # given the player's station with a hashtag in the name
        station = Station.objects.create(creator=player, name='#electronic')

        # when we call auto_fill() with the station
        with patch('teamplayer.lib.autofill.auto_fill_from_tags') \
                as auto_fill_from_tags:
            auto_fill_from_tags.return_value = [self.songfile] * 10
            player.queue.auto_fill(10, station=station)

        # then it calls auto_fill_from_tags()
        args, kwargs = auto_fill_from_tags.call_args
        self.assertEqual(kwargs['entries_needed'], 10)
        self.assertEqual(kwargs['station'], station)

        # and addes entries to the queue
        self.assertEqual(player.queue.entry_set.count(), 10)

    def test_auto_fill_user_station_without_hashtag(self):
        # given the player
        player = Player.objects.create_player('test', password='***')

        # given the player's station without a hashtag in the name
        station = Station.objects.create(creator=player, name='my station')

        # when we call auto_fill() with the station
        with patch('teamplayer.lib.autofill.auto_fill_from_tags') \
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
            with open(SILENCE, 'rb') as fp:
                silence = fp.read()
            filesize = len(silence)
            for i in range(10):
                filename = f"{i}.mp3"
                fullpath = os.path.join(tempdir, filename)
                with open(fullpath, 'wb') as fp:
                    fp.write(silence)
                LibraryItem.objects.create(
                    filename=fullpath,
                    artist="DJ Ango",
                    title=f"Song {i}",
                    album="Redundant",
                    filesize=filesize,
                    station_id=self.station.pk,
                    added_by=self.dj_ango,
                    length=301,
                )
            self.assertEqual(LibraryItem.objects.count(), 11)
            queue.auto_fill(
                max_entries=5,
                station=self.station,
                qs_filter={'length__lt': 600}
            )
            self.assertEqual(queue.entry_set.count(), 5)


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
            with open(SILENCE, 'rb') as fp:
                silence = fp.read()

            for data in song_data:
                filename = os.path.join(tempdir, f"{data[0]}-{data[1]}.mp3")
                with open(filename, "wb") as fp:
                    fp.write(silence)
                song = LibraryItem.objects.create(
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

    def test_create_station_reuses_users_old_station(self):
        # given the players's previous station
        station = Station.create_station('My Station', self.player)

        # when we disable the station
        station.enabled = False
        station.save()

        # and then create another station with the same player
        new_station = Station.create_station('My Other Station', self.player)

        # then the new_station is really the old station
        self.assertEqual(new_station.id, station.id)
        self.assertEqual(new_station.name, 'My Other Station')

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
        with open(SILENCE, 'rb') as songfile:
            entry = queue.add_song(UploadedFile(songfile), station=station)

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
        view = 'edit_station'
        post = {'station_id': station.pk,
                'action': 'rename',
                'name': 'TeamPlayer'}

        self.client.login(username='test', password='test')
        response = self.client.post(
            reverse(view),
            post,
            follow=True,
            HTTP_REFERRER=reverse('show_stations'))

        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content.decode())
        self.assertEqual(
            result,
            {'name': ['“TeamPlayer” is an invalid name.']}
        )

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

        current = self.spin.next(['The Time'])  # should play "Purple Rain"
        self.assertEqual(current[1], 'Prince')

        # should preempt Metallica and play The Time
        current = self.spin.next(['Prince'])
        self.assertEqual(current[1], 'The Time')

        # should preempt Metallica and play The Time
        current = self.spin.next()
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


class PlayLogTest(TestCase):
    """Tests for the PlayLog model"""
    def setUp(self):
        parent = super(PlayLogTest, self)
        parent.setUp()

        station = Station.main_station()
        artist = 'Earth, Wind & Fire'
        title = 'Fantasy'
        player = Player.dj_ango()
        time = timezone.now()

        self.playlog = PlayLog(
            artist=artist,
            player=player,
            station=station,
            time=time,
            title=title,
        )

    def test_str(self):
        # given the playlog entry
        playlog = self.playlog

        # when we call str() on it
        result = str(playlog)

        # then we get the expected string
        expected = (
            f"|{playlog.time}|Station {playlog.station.pk}: "
            "“Fantasy” by Earth, Wind & Fire"
        )
        self.assertEqual(result, expected)

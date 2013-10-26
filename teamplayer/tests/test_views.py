"""Unit tests for teamplayer views."""
import json
import re

import django.contrib.auth.models
import django.core.urlresolvers
import django.test

from mock import patch

from teamplayer.lib import users

from teamplayer.tests import utils

SpinDoctor = utils.SpinDoctor
TestCase = django.test.TestCase
reverse = django.core.urlresolvers.reverse
User = django.contrib.auth.models.User


class HomePageView(TestCase):

    """Tests for the home page view (exluding song list)"""
    def setUp(self):
        # create a user
        self.user = users.create_user(username='test', password='test')
        self.player = self.user.player
        self.client.login(username='test', password='test')
        self.url = reverse('teamplayer.views.home')
        self.client.get(self.url)

    def test_home(self):
        response = self.client.get(self.url, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_dj_name_appears(self):
        self.player.dj_name = 'Skipp Traxx'
        self.player.save()
        response = self.client.get(self.url, follow=True)
        self.assertContains(response, 'Skipp Traxx')

    @patch('teamplayer.lib.websocket.IPCHandler.send_message')
    def test_set_djname(self, mock):
        """Test that we can set the dj name in the view"""
        # This doesn't test the home page view per-se but it's an AJAX view
        # accessible via the home page
        url = reverse('teamplayer.views.change_dj_name')
        response = self.client.post(url, {'dj_name': u'Liquid X'})
        self.assertEqual(response.status_code, 204)
        user = User.objects.get(username='test')
        player = user.player
        self.assertEqual(player.dj_name, u'Liquid X')
        mock.assert_called_with(message_type='dj_name_change',
                                data={'dj_name': u'Liquid X',
                                      'previous_dj_name': '',
                                      'user_id': user.pk})

    @patch('teamplayer.lib.mpc.MPC.currently_playing')
    def test_song_display(self, mock):
        """Test that the currently playing area is working"""
        # Again, this is an AJAX view, also we need to monkey-patch
        # mpc.currently_playing() with a mock
        mock.return_value = {'dj': 'DJ Skipp Traxx',
                             'artist': 'Prince',
                             'title': 'Purple Rain',
                             'total_time': 99,
                             'remaining_time': 12,
                             'station_id': 1,
                             'artist_image': '/artist/Prince/image'}

        url = reverse('teamplayer.views.currently_playing')
        response = self.client.get(url)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['dj'], 'DJ Skipp Traxx')
        self.assertEqual(data['artist'], 'Prince')
        self.assertEqual(data['title'], 'Purple Rain')
        self.assertEqual(data['total_time'], 99)
        self.assertEqual(data['remaining_time'], 12)
        self.assertEqual(
            data['artist_image'],
            reverse('teamplayer.views.artist_image',
                    kwargs={'artist': 'Prince'}))

    @patch('teamplayer.lib.mpc.MPC.currently_playing')
    def test_currently_playing(self, mock):
        mock.return_value = {'dj': 'DJ Skipp Traxx',
                             'artist': 'Prince',
                             'title': 'Purple Rain',
                             'total_time': 99,
                             'remaining_time': 12,
                             'station_id': 1,
                             'artist_image': '/artist/Prince/image'}

        url = reverse('teamplayer.views.currently_playing')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['dj'], 'DJ Skipp Traxx')
        self.assertEqual(data['artist'], 'Prince')
        self.assertEqual(data['title'], 'Purple Rain')

    @patch('teamplayer.lib.mpc.MPC.currently_playing')
    def test_going_back_to_station(self, mock):
        """Show that we don't get infinite redirects when re-getting
        the station page"""
        response = self.client.get(self.url, follow=True)
        redirect_chain = response.redirect_chain
        self.assertLessEqual(len(redirect_chain), 1)


class ShowQueueView(TestCase):

    """Tests the teamplayer.views.show_queue view"""
    def setUp(self):
        # create a user
        self.user = users.create_user(username='test', password='test')
        self.player = self.user.player
        self.client.login(username='test', password='test')
        self.url = reverse('teamplayer.views.show_queue')

    def test_empty_queue(self):
        """Test that we get the appropriate info when we have an empty
        queue"""
        response = self.client.get(self.url)
        self.assertContains(response, '[]')

    def test_queue_with_songs(self):
        """Test that songs added show up in the list"""
        spin = SpinDoctor()
        spin.create_song_for(self.user, 'Prince', 'Purple Rain')
        response = self.client.get(self.url)
        self.assertContains(response, 'Prince')
        self.assertContains(response, 'Purple Rain')

    def test_queue_reordering(self):
        """Test that after re-ordering the queue it shows up in the new
        order Also tests that the reorder_queue view works"""
        spin = SpinDoctor()
        spin.create_song_for(self.user, 'Prince', 'Purple Rain')
        spin.create_song_for(self.user, 'Metallica', 'One')
        spin.create_song_for(self.user, 'Arcade Fire', 'Rococo')

        user = User.objects.get(username='test')
        player = user.player
        current_order = [x.id for x in player.queue.entry_set.all()]
        new_order = list(reversed(current_order))
        new_order_str = ','.join([str(i) for i in new_order])
        response = self.client.post(reverse('teamplayer.views.reorder_queue'),
                                    new_order_str, content_type='text/plain')

        returned_order = json.loads(response.content.decode('utf-8'))
        self.assertEqual(returned_order, new_order)
        response = self.client.get(self.url)
        match = re.search('Arcade Fire.*Metallica.*Prince',
                          response.content.decode('utf-8').replace('\n', ' '))
        self.assertNotEqual(match, None)

    @patch('teamplayer.lib.websocket.IPCHandler.send_message')
    def test_remove_from_queue(self, mock):
        """Tests that removing a song from the queue makes it no longer
        show in the list"""
        spin = SpinDoctor()
        spin.create_song_for(self.user, 'Prince', 'Purple Rain')

        response = self.client.get(self.url)
        self.assertContains(response, 'Purple Rain')
        song_id = self.user.player.queue.entry_set.all()[0].id

        response = self.client.delete(
            reverse('teamplayer.views.show_entry', args=(song_id,)))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Purple Rain')
        self.assertContains(response, '[]')

    @patch('teamplayer.lib.songs.get_similar_artists')
    def test_queue_after_song_plays(self, mock_call):
        """Test that song is removed from songlist when it plays"""
        spin = SpinDoctor()
        spin.create_song_for(self.user, 'Prince', 'Purple Rain')
        response = self.client.get(self.url)
        self.assertContains(response, 'Prince')
        self.assertContains(response, 'Purple Rain')

        spin.next()
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Prince')
        self.assertNotContains(response, 'Purple Rain')


class AddUserView(TestCase):

    """Test the add_user view"""

    def setUp(self):
        self.form_data = {
            'username': 'test',
            'password1': 'password',
            'password2': 'password',
        }

    def test_get_returns_200(self):
        response = self.client.get(reverse('teamplayer.views.registration'))
        self.assertEqual(response.status_code, 200)

    @patch('teamplayer.lib.websocket.IPCHandler.send_message')
    def test_can_add_user(self, mock):
        self.client.post(
            reverse('teamplayer.views.registration'), self.form_data)

        # check that the user exists
        test_user = User.objects.get(username=self.form_data['username'])

        # check that the user has a player and a queue
        self.assertTrue(test_user.player)
        self.assertTrue(hasattr(test_user.player, 'queue'))

    @patch('teamplayer.lib.websocket.IPCHandler.send_message')
    def test_user_already_exists(self, mock):
        form_data = self.form_data

        # add user
        self.client.post(reverse('teamplayer.views.registration'), form_data)

        # now add again
        response = self.client.post(reverse('teamplayer.views.registration'),
                                    form_data, follow=True)
        self.assertContains(response, 'already exists')


class RegistrationTest(TestCase):
    def test_no_player(self):
        """Show that we don't get the flash player in the registration view."""
        # when we access the registation page
        response = self.client.get(reverse('teamplayer.views.registration'))

        # Then it doesn't show up.
        self.assertNotContains(response, 'flashPlayer')

    def test_no_stations(self):
        """Show that we don't get the station links in the view."""
        # when we access the registation page
        response = self.client.get(reverse('teamplayer.views.register'))

        # Then it doesn't show up.
        self.assertNotContains(response, 'next station')

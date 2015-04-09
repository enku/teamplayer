from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import RequestFactory

from teamplayer.middleware import TeamPlayerMiddleware
from teamplayer.models import Player, Station


class TeamPlayerMiddlewareTestCase(TestCase):
    def setUp(self):
        self.player = Player.objects.create_player('test', password='test')
        self.request = RequestFactory().get('/')
        self.request.user = self.player.user
        self.request.session = {}

    def test_process_request(self):
        # Given the logged in user
        self.client.login(username='test', password='test')

        # And the request instance
        request = self.request

        # When passed to the middlware we get a player attribute
        middleware = TeamPlayerMiddleware()
        result = middleware.process_request(request)

        self.assertEqual(result, None)
        self.assertEqual(request.player, self.player)

    def test_user_with_no_player(self):
        # given the User with no Player
        user = User.objects.create_user(username='test2', password='***')

        # when we login and go to a page
        url = reverse('teamplayer.views.home')
        self.client.login(username='test2', password='***')
        self.client.get(url)

        # then the middleware gives the user a player object
        player = Player.objects.filter(user=user)
        self.assertEqual(player.count(), 1)

    def test_request_has_station(self):
        # Given the logged in user
        self.client.login(username='test', password='test')

        # And the request instance
        request = self.request

        # When passed to the middlware we get a station attribute
        middleware = TeamPlayerMiddleware()
        result = middleware.process_request(request)

        self.assertEqual(result, None)

        # it will be the main station because we haven't been anywhere else
        self.assertEqual(request.station, Station.main_station())

    def test_player_on_non_main_station(self):
        # given the second station
        station = Station.objects.create(
            creator=self.player, name='test station')

        # and the logged in user
        self.client.login(username='test', password='test')

        # when the user goes to that station
        url = reverse('station', args=[station.pk])
        self.client.get(url)

        # then goes to another view
        url = reverse('teamplayer.views.show_queue')
        response = self.client.get(url)

        # then the request object has the second station
        self.assertEqual(response.wsgi_request.station, station)

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import RequestFactory

from teamplayer.middleware import TeamPlayerMiddleware
from teamplayer.models import Player


class TeamPlayerMiddlewareTestCase(TestCase):
    def test_process_request(self):
        # Given the logged in user
        player = Player.objects.create_player('test', password='test')
        self.client.login(username='test', password='test')

        # And the request instance
        request = RequestFactory().get('/')
        request.user = player.user

        # When passed to the middlware we get a player attribute
        middleware = TeamPlayerMiddleware()
        result = middleware.process_request(request)

        self.assertEqual(result, None)
        self.assertEqual(request.player, player)

    def test_user_with_no_player(self):
        # given the User with no Player
        user = User.objects.create_user(username='test', password='***')

        # when we login and go to a page
        url = reverse('teamplayer.views.home')
        self.client.login(username='test', password='***')
        self.client.get(url)

        # then the middleware gives the user a player object
        player = Player.objects.filter(user=user)
        self.assertEqual(player.count(), 1)

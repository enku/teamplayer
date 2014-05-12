from teamplayer.middleware import TeamPlayerMiddleware
from teamplayer.models import Player

from django.test import TestCase
from django.test.client import RequestFactory


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

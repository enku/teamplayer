# pylint: disable=unused-argument
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from unittest_fixtures import Fixtures, given

from teamplayer.middleware import TeamPlayerMiddleware
from teamplayer.models import Player, Station

from . import lib


@given(lib.player, lib.request)
class TeamPlayerMiddlewareTestCase(TestCase):
    def test_process_request(self, fixtures: Fixtures) -> None:
        # Given the logged in user
        player = fixtures.player
        self.client.force_login(player.user)

        # And the request instance
        request = fixtures.request

        # And the get_response callable
        get_response = Mock()

        # When passed to the middleware we get a player attribute
        middleware = TeamPlayerMiddleware(get_response)
        response = middleware(request)

        self.assertEqual(response, get_response.return_value)
        self.assertEqual(request.player, player)

    @patch("teamplayer.lib.mpc.MPC")
    def test_user_with_no_player(self, mpc, fixtures: Fixtures) -> None:
        mpc.return_value.http_port = 8002
        mpc.return_value.currently_playing.return_value = {}

        # given the User with no Player
        user = User.objects.create_user(username="test2", password="***")

        # when we login and go to a page
        url = reverse("home")
        self.client.force_login(user)
        self.client.get(url)

        # then the middleware gives the user a player object
        player = Player.objects.filter(user=user)
        self.assertEqual(player.count(), 1)

    def test_request_has_station(self, fixtures: Fixtures) -> None:
        # Given the logged in user
        self.client.force_login(fixtures.player.user)

        # And the request instance
        request = fixtures.request

        # And the get_response callable
        get_response = Mock()

        # When passed to the middleware we get a station attribute
        middleware = TeamPlayerMiddleware(get_response)
        response = middleware(request)

        self.assertEqual(response, get_response.return_value)

        # it will be the main station because we haven't been anywhere else
        self.assertEqual(request.station, Station.main_station())

    @patch("teamplayer.lib.mpc.MPC")
    def test_player_on_non_main_station(self, mpc, fixtures: Fixtures) -> None:
        mpc.return_value.currently_playing.return_value = {}
        # given the second station
        station = Station.objects.create(creator=fixtures.player, name="test station")

        # and the logged in user
        self.client.force_login(fixtures.player.user)

        # when the user goes to that station
        url = reverse("station", args=[station.pk])
        self.client.get(url)

        # then goes to another view
        url = reverse("show_queue")
        response = self.client.get(url)

        # then the request object has the second station
        self.assertEqual(response.wsgi_request.station, station)

    def test_station_in_session_does_not_exist(self, fixtures: Fixtures) -> None:
        # given the middleware
        middleware = TeamPlayerMiddleware(Mock())

        # given the non-existing station_id
        station_id = -1
        assert not Station.objects.filter(pk=station_id).exists()

        # when the request session has the bogus station id and
        # process_request is called
        request = fixtures.request
        request.session["station_id"] = station_id
        middleware(request)

        # then the request gets put on the main station
        self.assertEqual(request.station, Station.main_station())

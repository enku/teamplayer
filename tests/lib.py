"""Fixures and utilities for teamplayer tests"""

# pylint: disable=redefined-outer-name
from unittest import mock

from django.core.handlers.wsgi import WSGIRequest
from django.test.client import RequestFactory
from unittest_fixtures import FixtureContext, Fixtures, fixture

from teamplayer.models import Player, Station


@fixture()
def player(_: Fixtures, username: str = "test", password: str = "test") -> Player:
    return Player.objects.create_player(username=username, password=password)


@fixture(player)
def station(
    fixtures: Fixtures, creator: str | None = None, name: str | None = None
) -> Station:
    if creator is None:
        player = fixtures.player
    else:
        player = Player.objects.get(user__username=creator)

    user = player.user
    name = name or f"{user.username}'s station"

    return Station.objects.create(creator=player, name=name)


@fixture()
def station_thread(_: Fixtures) -> FixtureContext[mock.Mock]:
    with mock.patch(
        "teamplayer.management.commands.spindoctor.StationThread", autospec=True
    ) as station_thread:
        yield station_thread


@fixture()
def start_socket_server(_: Fixtures) -> FixtureContext[mock.Mock]:
    with mock.patch(
        "teamplayer.management.commands.spindoctor.start_socket_server", autospec=True
    ) as sss:
        yield sss


@fixture()
def shutdown(_: Fixtures) -> FixtureContext[mock.Mock]:
    with mock.patch(
        "teamplayer.management.commands.spindoctor.shutdown", autospec=True
    ) as shutdown:
        yield shutdown


@fixture(player)
def request(
    fixtures: Fixtures,
    player: Player | None = None,
    method: str = "get",
    path: str = "/",
) -> WSGIRequest:
    player = player or fixtures.player
    request_factory = RequestFactory()
    request_method = getattr(request_factory, method)
    request = request_method(path)
    request.user = player.user
    request.session = {}

    return request

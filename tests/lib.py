"""Fixures and utilities for teamplayer tests"""

# pylint: disable=redefined-outer-name
import tempfile
from typing import Any
from unittest import mock

from django.core.handlers.wsgi import WSGIRequest
from django.test.client import Client, RequestFactory
from unittest_fixtures import FixtureContext, Fixtures, fixture

from teamplayer.lib.mpc import MPC
from teamplayer.models import Player, Station


@fixture()
def client(_: Fixtures) -> Client:
    return Client()


@fixture(client)
def player(
    fixtures: Fixtures,
    username: str = "test",
    password: str = "test",
    login: bool = False,
) -> Player:
    player = Player.objects.create_player(username=username, password=password)

    if login:
        fixtures.client.force_login(player.user)

    return player


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


@fixture()
def tempdir(_: Fixtures) -> FixtureContext[str]:
    """Temporary directory fixture"""
    with tempfile.TemporaryDirectory() as tempdir:
        yield tempdir


@fixture()
def mpc(
    _: Fixtures, port: int = 8002, currently_playing: dict[str, Any] | None = None
) -> FixtureContext[MPC]:
    with mock.patch("teamplayer.lib.mpc.MPC") as mpc:
        mpc.return_value.http_port = port
        mpc.return_value.currently_playing.return_value = currently_playing or {
            "dj": "DJ Skipp Traxx",
            "artist": "Prince",
            "title": "Purple Rain",
            "total_time": 99,
            "remaining_time": 12,
            "station_id": 1,
            "artist_image": "/artist/Prince/image",
        }
        yield mpc

"""Fixures and utilities for teamplayer tests"""

# pylint: disable=redefined-outer-name

from unittest_fixtures import fixture, Fixtures
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

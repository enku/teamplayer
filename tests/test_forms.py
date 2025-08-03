"""Tests for TeamPlayer forms"""

import django.test

from unittest_fixtures import given, Fixtures, where
from teamplayer.forms import EditStationForm

from . import lib


@given(lib.player, lib.station, player2=lib.player, station2=lib.station)
@where(player2__username="player2", station2__creator="player2")
class EditStationTests(django.test.TestCase):
    def test(self, fixtures: Fixtures) -> None:
        data = {"name": "test", "action": "rename", "station_id": fixtures.station.pk}
        form = EditStationForm(data)

        self.assertTrue(form.is_valid(), form.errors)

    def test_station_named_teamplayer(self, fixtures: Fixtures) -> None:
        data = {
            "name": "teamplayer",
            "action": "rename",
            "station_id": fixtures.station.pk,
        }
        form = EditStationForm(data)
        self.assertFalse(form.is_valid())

        self.assertEqual({"name": ["“teamplayer” is an invalid name."]}, form.errors)

    def test_station_name_length(self, fixtures: Fixtures) -> None:
        data = {
            "name": "x" * 129,
            "action": "rename",
            "station_id": fixtures.station.pk,
        }
        form = EditStationForm(data)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"name": ["Ensure this value has at most 128 characters (it has 129)."]},
            form.errors,
        )

    def test_station_already_exisiting_name(self, fixtures: Fixtures) -> None:
        data = {
            "name": fixtures.station2.name,
            "action": "rename",
            "station_id": fixtures.station.pk,
        }
        form = EditStationForm(data)

        self.assertFalse(form.is_valid())
        self.assertEqual({"__all__": ["That name is already taken."]}, form.errors)

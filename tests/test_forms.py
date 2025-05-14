"""Tests for TeamPlayer forms"""

import django.test

from teamplayer.forms import EditStationForm
from teamplayer.models import Player, Station


class EditStationTests(django.test.TestCase):
    def setUp(self) -> None:
        self.player = Player.objects.create_player(username="test", password="test")
        self.station = Station.objects.create(creator=self.player)

    def test(self) -> None:
        data = {"name": "test", "action": "rename", "station_id": self.station.pk}
        form = EditStationForm(data)

        self.assertTrue(form.is_valid(), form.errors)

    def test_station_named_teamplayer(self) -> None:
        data = {"name": "teamplayer", "action": "rename", "station_id": self.station.pk}
        form = EditStationForm(data)
        self.assertFalse(form.is_valid())

        self.assertEqual({"name": ["“teamplayer” is an invalid name."]}, form.errors)

    def test_station_name_length(self) -> None:
        data = {"name": "x" * 129, "action": "rename", "station_id": self.station.pk}
        form = EditStationForm(data)

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"name": ["Ensure this value has at most 128 characters (it has 129)."]},
            form.errors,
        )

    def test_station_already_exisiting_name(self) -> None:
        player2 = Player.objects.create_player(username="player2", password="test")
        Station.objects.create(creator=player2, name="test")
        data = {"name": "test", "action": "rename", "station_id": self.station.pk}
        form = EditStationForm(data)

        self.assertFalse(form.is_valid())
        self.assertEqual({"__all__": ["That name is already taken."]}, form.errors)

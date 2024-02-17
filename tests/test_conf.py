"""Tests for TeamPlayerSettings"""

# pylint: disable=missing-class-docstring,missing-function-docstring
from unittest import TestCase

from teamplayer.conf import TeamPlayerSettings


class SettingsTestCase(TestCase):
    def test_from_dict(self) -> None:
        data_dict = {
            "TEAMPLAYER_WEBSOCKET_PORT": "8000",
            "TODAY_IS": "your birthday",
            "TODAY_WEBSOCKET_PORT": "9000",
            "TODAY_MPD_HOME": "/foo/bar",
            "TODAY_SHAKE_THINGS_UP_FILTER": '{"this": "that"}',
        }
        prefix = "TODAY_"

        settings = TeamPlayerSettings.from_dict(prefix, data_dict)

        self.assertEqual(settings.MPD_HOME, "/foo/bar")
        self.assertEqual(settings.QUEUE_DIR, "/foo/bar/queue")
        self.assertEqual(settings.WEBSOCKET_PORT, 9000)
        self.assertEqual(settings.SHAKE_THINGS_UP_FILTER, {"this": "that"})

        with self.assertRaises(AttributeError):
            settings.IS  # pylint: disable=no-member,pointless-statement

"""Tests for the spindoctor management command"""

import os
import signal
from unittest import mock
from unittest_fixtures import given, Fixtures

from django.core.management import call_command
from django.test import TestCase

from teamplayer.conf import settings
from teamplayer.management.commands import spindoctor
from teamplayer.models import Player, Queue, Station

from . import lib


# pylint: disable=unused-argument
@given(lib.station, lib.station_thread, lib.start_socket_server, lib.shutdown)
class SpinDoctorCommandTestCase(TestCase):
    def test_updates_dj_angos_queue(self, fixtures: Fixtures) -> None:
        dj_ango = Player.dj_ango()
        queue: Queue = dj_ango.queue
        queue.active = True
        queue.save()

        call_command("spindoctor")

        queue.refresh_from_db()
        self.assertFalse(queue.active)

    def test_creates_station_threads(self, fixtures: Fixtures) -> None:
        station = fixtures.station
        stations = list(Station.objects.all())
        self.assertEqual(len(stations), 2)

        call_command("spindoctor")

        station_thread = fixtures.station_thread
        station_thread.create.assert_has_calls(
            [mock.call(station), mock.call(Station.main_station())], any_order=True
        )

    def test_starts_socket_server(self, fixtures: Fixtures) -> None:
        call_command("spindoctor")

        start_socket_server = fixtures.start_socket_server
        start_socket_server.assert_called_once_with()

    @mock.patch("teamplayer.management.commands.spindoctor.setproctitle")
    def test_starts_sets_process_title(
        self, setproctitle: mock.Mock, fixtures: Fixtures
    ) -> None:
        call_command("spindoctor")

        setproctitle.assert_called_once_with("spindoctor")

    def test_shuts_down_on_keyboard_interrupt(self, fixtures: Fixtures) -> None:
        start_socket_server = fixtures.start_socket_server
        start_socket_server.side_effect = KeyboardInterrupt()

        call_command("spindoctor")

        shutdown = fixtures.shutdown
        shutdown.assert_called_once_with()

    def test_shuts_down_on_exceptions(self, fixtures: Fixtures) -> None:
        start_socket_server = fixtures.start_socket_server
        start_socket_server.side_effect = RuntimeError("Kaboom!")

        call_command("spindoctor")

        shutdown = fixtures.shutdown
        shutdown.assert_called_once_with()


@given(lib.station_thread)
@mock.patch("teamplayer.management.commands.spindoctor.os.kill")
class ShutdownTestCase(TestCase):
    def test_suicide(self, kill: mock.Mock, fixtures: Fixtures) -> None:
        spindoctor.shutdown()

        kill.assert_called_once_with(os.getpid(), signal.SIGTERM)

    def test_shuts_down_station_threads(
        self, _kill: mock.Mock, fixtures: Fixtures
    ) -> None:
        threads = {i: mock.Mock() for i in range(5)}
        station_thread = fixtures.station_thread
        station_thread.get_all.return_value = threads

        spindoctor.shutdown()

        for thread in threads.values():
            thread.mpc.stop.assert_called_once_with()


@mock.patch("teamplayer.management.commands.spindoctor.tornado.web.Application")
@mock.patch("teamplayer.management.commands.spindoctor.tornado.ioloop.IOLoop.instance")
class StartSocketServerTestCase(TestCase):
    def test_starts_tornado_app(self, _ioloop: mock.Mock, app: mock.Mock) -> None:
        spindoctor.start_socket_server()

        app_obj = app.return_value
        app_obj.listen.assert_called_once_with(settings.WEBSOCKET_PORT)

    def test_starts_ioloop(self, ioloop: mock.Mock, _app: mock.Mock) -> None:
        spindoctor.start_socket_server()

        ioloop_obj = ioloop.return_value
        ioloop_obj.start.assert_called_once_with()

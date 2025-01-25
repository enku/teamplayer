"""Tests for the spindoctor management command"""

import os
import signal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from teamplayer.conf import settings
from teamplayer.management.commands import spindoctor
from teamplayer.models import Player, Queue, Station


@mock.patch("teamplayer.management.commands.spindoctor.StationThread")
@mock.patch("teamplayer.management.commands.spindoctor.start_socket_server")
class SpinDoctorCommandTestCase(TestCase):
    def test_updates_dj_angos_queue(
        self, _start_socket_server: mock.Mock, _station_thread: mock.Mock
    ) -> None:
        dj_ango = Player.dj_ango()
        queue: Queue = dj_ango.queue
        queue.active = True
        queue.save()

        call_command("spindoctor")

        queue.refresh_from_db()
        self.assertFalse(queue.active)

    def test_creates_station_threads(
        self, _start_socket_server: mock.Mock, station_thread: mock.Mock
    ) -> None:
        player = Player.objects.create_player(username="test", password="test")
        station = Station.objects.create(creator=player)
        stations = list(Station.objects.all())
        self.assertEqual(len(stations), 2)

        call_command("spindoctor")

        station_thread.create.assert_has_calls(
            [mock.call(station), mock.call(Station.main_station())], any_order=True
        )

    def test_starts_socket_server(
        self, start_socket_server: mock.Mock, _station_thread: mock.Mock
    ) -> None:
        call_command("spindoctor")

        start_socket_server.assert_called_once_with()

    @mock.patch("teamplayer.management.commands.spindoctor.setproctitle")
    def test_starts_sets_process_title(
        self,
        setproctitle: mock.Mock,
        _start_socket_server: mock.Mock,
        _station_thread: mock.Mock,
    ) -> None:
        call_command("spindoctor")

        setproctitle.assert_called_once_with("spindoctor")

    @mock.patch("teamplayer.management.commands.spindoctor.shutdown")
    def test_shuts_down_on_keyboard_interrupt(
        self,
        shutdown: mock.Mock,
        start_socket_server: mock.Mock,
        _station_thread: mock.Mock,
    ) -> None:
        start_socket_server.side_effect = KeyboardInterrupt()

        call_command("spindoctor")

        shutdown.assert_called_once_with()

    @mock.patch("teamplayer.management.commands.spindoctor.shutdown")
    def test_shuts_down_on_exceptions(
        self,
        shutdown: mock.Mock,
        start_socket_server: mock.Mock,
        _station_thread: mock.Mock,
    ) -> None:
        start_socket_server.side_effect = RuntimeError("Kaboom!")

        call_command("spindoctor")

        shutdown.assert_called_once_with()


@mock.patch("teamplayer.management.commands.spindoctor.os.kill")
class ShutdownTestCase(TestCase):
    def test_suicide(self, kill: mock.Mock) -> None:
        spindoctor.shutdown()

        kill.assert_called_once_with(os.getpid(), signal.SIGTERM)

    @mock.patch("teamplayer.management.commands.spindoctor.StationThread")
    def test_shuts_down_station_threads(
        self, station_thread: mock.Mock, _kill: mock.Mock
    ) -> None:
        threads = {i: mock.Mock() for i in range(5)}
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

"""Tests for the shutdown management command"""

from unittest import TestCase, mock

from django.core.management import call_command


@mock.patch("teamplayer.management.commands.shutdown.IPCHandler")
class ShutdownTestCase(TestCase):
    def test(self, ipc_handler) -> None:
        call_command("shutdown")

        ipc_handler.send_message.assert_called_once_with("shutdown", None)

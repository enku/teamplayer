"""
Stop the spindoctor
"""

from django.core.management.base import BaseCommand

from teamplayer.lib.websocket import IPCHandler


class Command(BaseCommand):
    """Command to stop the spindoctor"""
    help = "Stop the TeamPlayer service"

    def handle(self, *args, **options):
        IPCHandler.send_message('shutdown', None)

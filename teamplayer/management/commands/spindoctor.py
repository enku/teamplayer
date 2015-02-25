"""Spin Doctor management command for the teamplayer app

This command is responsible for starting the mpd daemons and continually
grabbing entries from users' queues and adding them to the mpd playlist
"""
import logging
import os
import re
import signal
from optparse import make_option
from time import sleep

from django.core.management.base import BaseCommand

from teamplayer import models
from teamplayer.conf import settings
from teamplayer.lib.daemon import createDaemon
from teamplayer.lib.threads import SocketServer, StationThread

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = lambda x: None


PLAYING_REGEX = re.compile(
    r'^\[playing\] #\d+/\d+ +(\d+:\d{2})/(\d+:\d{2}) .*')

LOGGER = logging.getLogger('teamplayer.spindoctor')


class Command(BaseCommand):
    """The actual "spindoctor" admin command"""
    help = "Hey DJ play that song!"

    option_list = BaseCommand.option_list + (
        make_option(
            '-d',
            action='store_true',
            dest='daemonize',
            default=False,
            help='Run in the background',
        ),
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        setproctitle('spindoctor')
        self.options = {}
        self.previous_user = None
        self.previous_song = None
        self.running = False
        self.socket_server = SocketServer(name='Socket Server')

    def handle(self, *args, **options):
        if options['daemonize']:
            createDaemon()

        self.update_dj_ango_queue()
        LOGGER.info('Starting StationThreads')
        for station in models.Station.get_stations():
            StationThread.create(station)

        self.socket_server.start()

        self.running = True
        while self.running:
            try:
                signal.pause()
            except Exception:
                LOGGER.error('Error inside main loop', exc_info=True)
                LOGGER.error('Attempting to continue...')
                sleep(3)
                continue
            except KeyboardInterrupt:
                self.shutdown()

    def update_dj_ango_queue(self):
        queue = models.Player.dj_ango().queue
        queue.active = settings.ALWAYS_SHAKE_THINGS_UP
        queue.save()

    def shutdown(self):
        """Shut down mpd servers and exit"""
        LOGGER.critical('Shutting down')
        for station_thread in StationThread.get_all().values():
            station_thread.mpc.stop()

        # suicide
        os.kill(os.getpid(), signal.SIGTERM)


LOGGER.info('TeamPlayer: DJ Ango at your service!')

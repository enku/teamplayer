"""Spin Doctor management command for the teamplayer app

This command is responsible for starting the mpd daemons and continually
grabbing entries from users' queues and adding them to the mpd playlist
"""
import logging
import os
import re
import signal
import sys
from optparse import make_option

from django.core.management.base import BaseCommand

from teamplayer import models
from teamplayer.conf import settings
from teamplayer.lib.daemon import createDaemon
from teamplayer.lib.threads import StationThread, start_socket_server

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

    def handle(self, *args, **options):
        if options['daemonize']:
            createDaemon()

        self.update_dj_ango_queue()
        LOGGER.info('Starting StationThreads')
        for station in models.Station.get_stations():
            StationThread.create(station)

        self.running = True
        while self.running:
            try:
                start_socket_server()
            except Exception:
                LOGGER.exception('Error inside main loop')
                LOGGER.error('Attempting to shutdown...')
                self.shutdown()
                return
            except KeyboardInterrupt:
                self.shutdown()

    def update_dj_ango_queue(self):
        queue = models.Player.dj_ango().queue
        queue.active = settings.ALWAYS_SHAKE_THINGS_UP
        queue.save()

    def shutdown(self):
        """Shut down mpd servers and exit"""
        csi = '\x1b['
        sys.stderr.write('{csi}1G'.format(csi=csi))  # move to start of line
        LOGGER.critical('Shutting down')
        for station_thread in StationThread.get_all().values():
            station_thread.mpc.stop()

        # suicide
        os.kill(os.getpid(), signal.SIGTERM)


LOGGER.info('TeamPlayer: DJ Ango at your service!')

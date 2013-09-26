# -*- coding: utf-8 -*-
"""Spin Doctor management command for the teamplayer app

This command is responsible for starting the mpd daemons and continually
grabbing entries from users' queues and adding them to the mpd playlist
"""
import logging
from optparse import make_option
import os
import re
import signal
from time import sleep

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = lambda x: None

from teamplayer.conf import settings
from teamplayer.lib import songs
from teamplayer.lib.threads import SocketServer, StationThread
from teamplayer.lib.websocket import SocketHandler
from teamplayer.lib.daemon import createDaemon
from teamplayer import models
from teamplayer.lib.signals import SONG_CHANGE

PLAYING_REGEX = re.compile(
    r'^\[playing\] #\d+/\d+ +(\d+:\d{2})/(\d+:\d{2}) .*')

LOGGER = logging.getLogger('teamplayer.spindoctor')


def scrobble_song(sender, **kwargs):
    """Signal handler to scrobble when a song changes."""
    station_id = kwargs['station_id']

    # only the Main Station scrobbles
    if station_id != models.Station.main_station().id:
        return

    previous_song = kwargs['previous_song']
    current_song = kwargs['current_song']

    if previous_song and previous_song['artist'] != 'DJ Ango':
        LOGGER.debug(u'Scrobbling “%s” by %s',
                     previous_song['title'],
                     previous_song['artist'])
        songs.scrobble_song(previous_song)
    if current_song['artist'] != 'DJ Ango':
        LOGGER.debug(u'Currently playing “%s” by %s',
                     current_song['title'],
                     current_song['artist'])
        songs.scrobble_song(current_song, now_playing=True)


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

        SONG_CHANGE.connect(SocketHandler.notify_clients)

        if settings.SCROBBLER_USER:
            # Set up the Scrobber
            SONG_CHANGE.connect(scrobble_song)

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
        queue = User.dj_ango().userprofile.queue
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

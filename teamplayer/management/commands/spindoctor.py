"""Spin Doctor management command for the teamplayer app

This command is responsible for starting the mpd daemons and continually
grabbing entries from users' queues and adding them to the mpd playlist
"""
import asyncio
import os
import signal
import sys

import tornado.web
from django.core.management.base import BaseCommand
from tornado.platform.asyncio import AnyThreadEventLoopPolicy

from teamplayer import logger, models
from teamplayer.conf import settings
from teamplayer.lib.comm import StationThread
from teamplayer.lib.websocket import IPCHandler, SocketHandler

try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = None


class Command(BaseCommand):
    """The actual "spindoctor" admin command"""

    help = "Hey DJ play that song!"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        if setproctitle:
            setproctitle("spindoctor")

    def handle(self, *args, **options):
        # If we don't do this then we have to manually creat an asyncio loop in
        # each thread where we want do work with tornado. Since threads
        # spindoctor threads in teamplayer are dynamic and all use tornado, the
        # below ensures that every thread (in this process) has an event loop
        asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

        # Update DJ Ango's queue according to ALWAYS_SHAKE_THINGS_UP
        queue = models.Player.dj_ango().queue
        queue.active = settings.ALWAYS_SHAKE_THINGS_UP
        queue.save()

        logger.info("Starting StationThreads")
        for station in models.Station.get_stations():
            StationThread.create(station)

        try:
            start_socket_server()
        except Exception:
            logger.exception("Error inside main loop")
            logger.error("Attempting to shutdown...")
            shutdown()
        except KeyboardInterrupt:
            shutdown()


def shutdown():
    """Shut down mpd servers and exit"""
    csi = "\x1b["
    sys.stderr.write(f"{csi}1G")  # move to start of line
    logger.critical("Shutting down")
    for station_thread in StationThread.get_all().values():
        station_thread.mpc.stop()

    # suicide
    os.kill(os.getpid(), signal.SIGTERM)


def start_socket_server():
    """Start the tornado event loop"""
    logger.debug("Tornado has started")
    application = tornado.web.Application(
        [
            (r"/", SocketHandler),
            (r"/ipc", IPCHandler),
        ]
    )
    application.listen(settings.WEBSOCKET_PORT)

    tornado.ioloop.IOLoop.instance().start()


logger.info("TeamPlayer: DJ Ango at your service!")

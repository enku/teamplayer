import functools
import logging
import os
import shutil
import signal
import sys
import time
from json import dumps, loads

import tornado.gen
import tornado.ioloop
import tornado.web
import tornado.websocket
from django.conf import settings as django_settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.urlresolvers import reverse
from mutagen import File

from teamplayer import models
from teamplayer.conf import settings
from teamplayer.lib import (
    get_player_from_session_id,
    get_random_filename,
    get_station_id_from_session_id,
    remove_pedantic,
    signals
)
from teamplayer.serializers import StationSerializer
from tp_library.models import SongFile

LOGGER = logging.getLogger('teamplayer.websockets')


class SocketHandler(tornado.websocket.WebSocketHandler):
    clients = []

    def open(self):
        LOGGER.debug('WebSocket connection opened')
        station_id = None
        self.clients.append(self)
        self.broadcast_player_stats()
        self.player = None

        if 'sessionid' in self.request.cookies:
            session_id = self.request.cookies['sessionid'].value
            try:
                self.player = get_player_from_session_id(session_id)
            except ObjectDoesNotExist:
                pass

            station_id = get_station_id_from_session_id(session_id)

        if station_id and self.player:
            current_song = models.Station.objects.get(
                pk=station_id).current_song()

            self.message(self.player, 'song_change', current_song)

        self.broadcast('new_connection', self.player.username, exclude=[self])

    def on_close(self):
        LOGGER.debug('WebSocket connection closed')
        self.clients.remove(self)
        self.broadcast_player_stats()

    def on_pong(self, message):
        pass

    def check_origin(self, origin):
        return True

    @classmethod
    def message(cls, player, message_type, data):
        """Send a message to all connections associated with player"""
        clients = [i for i in cls.clients if i.player == player]
        for client in clients:
            client.write_message(dumps(
                {
                    'type': message_type,
                    'data': data,
                }
            ))
        return len(clients)

    @classmethod
    def broadcast(cls, message_type, data, exclude=None):
        exclude = exclude or []
        for client in cls.clients:
            if client in exclude:
                continue
            client.write_message(dumps(
                {
                    'type': message_type,
                    'data': data,
                }
            ))

    @classmethod
    def broadcast_player_stats(cls):
        stats = models.Player.player_stats()
        stats['users'] = len(cls.clients)
        cls.broadcast('user_stats', stats)

    @classmethod
    def broadcast_station_stats(cls):
        stations = models.Station.get_stations()
        for client in cls.clients:
            client.write_message(dumps({
                'type': 'station_stats',
                'data': StationSerializer(
                    stations,
                    many=True,
                    context={'request': client.request}).data
            }))

    @classmethod
    @tornado.gen.coroutine
    def notify_clients(cls, **kwargs):
        """Signal handler to send a message to clients when the song changes.
        """
        current_song = kwargs['current_song']
        cls.broadcast(
            'song_change',
            current_song,
        )
        cls.broadcast_player_stats()
        cls.broadcast_station_stats()


class IPCHandler(tornado.websocket.WebSocketHandler):

    """
    WebSocketHandler for ipc messages.
    """
    conn = None

    def open(self):
        LOGGER.debug('IPC connection opened')

    def on_message(self, message):
        """Handle message"""
        message = loads(message)

        if message.get('key') != django_settings.SECRET_KEY:
            LOGGER.critical('Someone is trying to hack me!', extra=message)
            return

        message_type = message['type']
        data = message['data']
        handler_name = 'handle_%s' % message_type
        LOGGER.debug('Message received: %s', message_type)

        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            handler(data)

    @staticmethod
    def get_conn():
        url = 'ws://localhost:%s/ipc' % settings.WEBSOCKET_PORT
        ioloop = tornado.ioloop.IOLoop.current()
        conn = ioloop.run_sync(functools.partial(
            tornado.websocket.websocket_connect, url))
        return conn

    @classmethod
    def send_message(cls, message_type, data):
        """
        Create a websocket connection and send a message to the handler.
        """
        cls.conn = cls.conn or cls.get_conn()
        cls.conn.write_message(dumps(
            {
                'type': message_type,
                'key': django_settings.SECRET_KEY,
                'data': data,
            }
        ))

# - Message Handlers ----------------------------------------------------------
    def handle_wall(self, message):
        """Handler for wall messages."""
        SocketHandler.broadcast('wall', message)

    def handle_song_added(self, song_id):
        signals.song_added.send(models.Entry, song_id=song_id)
        SocketHandler.broadcast_player_stats()
        SocketHandler.broadcast_station_stats()

        signals.QUEUE_CHANGE_EVENT.set()
        signals.QUEUE_CHANGE_EVENT.clear()

    def handle_song_removed(self, song_id):
        signals.song_removed.send(models.Entry, song_id=song_id)
        SocketHandler.broadcast_player_stats()
        SocketHandler.broadcast_station_stats()

    def handle_queue_status(self, data):
        # Update the status widget thingie
        SocketHandler.broadcast_player_stats()
        SocketHandler.broadcast_station_stats()

        # Send an event to the spindoctor
        signals.QUEUE_CHANGE_EVENT.set()
        signals.QUEUE_CHANGE_EVENT.clear()

    def handle_shutdown(self, data):
        """Shut down all services"""
        from teamplayer.lib.threads import StationThread

        LOGGER.critical('Shutting down')
        for station_thread in StationThread.get_all().values():
            station_thread.mpc.stop()

        # suicide
        os.kill(os.getpid(), signal.SIGTERM)
        sys.exit(0)

    def handle_station_rename(self, data):
        """A station's name has changed"""
        SocketHandler.broadcast('station_rename', data)
        SocketHandler.broadcast_station_stats()

    def handle_station_delete(self, station_id):
        """A station has been removed."""
        # to avoid circular imports
        from teamplayer.lib.threads import StationThread

        # first we broadcast so that all clients can get off the station
        SocketHandler.broadcast('station_delete', station_id)
        SocketHandler.broadcast_player_stats()
        SocketHandler.broadcast_station_stats()

        # give 'em a while
        time.sleep(3)

        StationThread.remove(station_id)
        signals.station_delete.send(models.Station, station_id=station_id)

    def handle_station_create(self, station_id):
        """A station was created. we need to start the Thread"""
        # to avoid circular imports
        from teamplayer.lib.threads import StationThread

        try:
            station = models.Station.objects.get(pk=station_id)
        except models.Station.DoesNotExist:
            return

        LOGGER.debug('Creating thread for new station: %s', station)
        StationThread.create(station)
        signals.station_create.send(models.Station, station_id=station_id)

        # Let 'em know
        for client in SocketHandler.clients:
            request = client.request
            client.write_message(dumps({
                'type': 'station_create',
                'data': StationSerializer(
                    station,
                    context={'request': request}).data
            }))
        SocketHandler.broadcast_player_stats()
        SocketHandler.broadcast_station_stats()

    def handle_library_add(self, entry_id):
        """Add an entry to the TeamPlayer library."""
        entry = models.Entry.objects.get(pk=entry_id)
        LOGGER.debug('Adding %s to Library.', entry)
        filename = get_random_filename(entry.filetype)
        fullpath = os.path.join(settings.UPLOADED_LIBRARY_DIR, filename)
        entry_name = os.path.join(django_settings.MEDIA_ROOT, entry.song.name)

        # first try a cheap and dirty link
        try:
            os.link(entry_name, fullpath)
        except OSError:
            try:
                shutil.copy(entry_name, fullpath)
            except Exception:
                # Ok, I give up
                logging.exception(
                    'Error copying {0} to library.'.format(filename),
                    exc_info=True
                )
                return

        # try to add it to the library
        metadata = File(fullpath, easy=True)

        # this should never happen, but..
        if not metadata:
            os.unlink(fullpath)

        try:
            songfile, created = SongFile.metadata_get_or_create(
                fullpath, metadata, entry.queue.player, entry.station.pk)
        except ValidationError as error:
            msg = 'Error adding file to library: %s' % str(error)
            logging.debug(msg)
            created = False

        if created:
            song_info = {
                'station_id': songfile.station_id,
                'title': songfile.title,
                'artist': songfile.artist,
                'artist_image': reverse('teamplayer.views.artist_image',
                                        kwargs={'artist': songfile.artist}),
                'total_time': songfile.length,
                'path': songfile.filename,
            }
            signals.library_add.send(
                models.Player,
                player=entry.queue.player,
                song_info=song_info,
            )
        else:
            os.unlink(fullpath)

    def handle_dj_name_change(self, data):
        SocketHandler.broadcast(
            'dj_name_change',
            {
                'previous_dj_name': data['previous_dj_name'],
                'dj_name': data['dj_name'],
            },
        )

    def handle_user_created(self, data):
        SocketHandler.broadcast('roster_change', data)
# -----------------------------------------------------------------------------

remove_pedantic()

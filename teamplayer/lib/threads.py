"""Thread classes and helpers for TeamPlayer."""
import logging
import queue
import shutil
import threading
from time import sleep

import tornado.gen
import tornado.web

from teamplayer.conf import settings
from teamplayer.lib import copy_entry_to_queue, songs
from teamplayer.lib.mpc import MPC
from teamplayer.lib.signals import QUEUE_CHANGE_EVENT
from teamplayer.lib.websocket import IPCHandler, SocketHandler
from teamplayer.models import Mood, Player, Station
from teamplayer.serializers import EntrySerializer

LOGGER = logging.getLogger('teamplayer.threads')


@tornado.gen.coroutine
def scrobble_song(song, now_playing=False):
    """Signal handler to scrobble when a song changes."""
    # only the Main Station scrobbles
    if song and song['artist'] != 'DJ Ango':
        LOGGER.debug(u'Scrobbling “%s” by %s', song['title'], song['artist'])
        songs.scrobble_song(song, now_playing=now_playing)


class Mooder(threading.Thread):
    """Thread for handling the mood

    This Thread will listen on a queue for artist to set moods for and set
    update the mood database indefinately
    """
    def __init__(self, *args, **kwargs):
        self.station = kwargs.pop('station')
        super(Mooder, self).__init__(*args, **kwargs)

    def run(self):
        LOGGER.info('%s has started', self.name)
        self.running = True
        while self.running:
            artist = self.queue.get()
            if artist == 'Unknown':
                continue
            LOGGER.debug(u'Logging mood for %s', artist)
            Mood.log_mood(artist, self.station)
            self.queue.task_done()

    def stop(self):
        LOGGER.info('%s shutting down.' % self.name)
        self.running = False
        self.queue.put('Unknown')


class StationThread(threading.Thread):
    """Class to handle stations, starting/stopping their mpds
    and the creation/removal process.
    """
    __station_threads = {}
    __lock = threading.Lock()

    secs_to_inject_new_song = settings.CROSSFADE + 1.5

    def __init__(self, *args, **kwargs):
        self.station = kwargs.pop('station')
        super(StationThread, self).__init__(*args, **kwargs)
        name = 'Station %s' % (self.name if self.station else '0')

        self.running = False
        self.mpc = MPC(self.station)
        self.scrobble = (settings.SCROBBLER_USER
                         and self.station == Station.main_station())
        self.previous_player = None
        self.previous_song = None

        # set up the Mood thread
        self.mooder = Mooder(
            name='Mooder for %s' % name,
            station=self.station,
        )
        self.mooder.daemon = True
        self.mooder.queue = queue.Queue()

    @classmethod
    def create(cls, station):
        """Create and return a StationThread.

        If the StationThread associated with station already exists, simply
        return that thread.
        """
        with cls.__lock:
            if station.pk in cls.__station_threads:
                return cls.__station_threads[station.pk]

            station_thread = StationThread(name='Station %s' % station.pk,
                                           station=station)
            cls.__station_threads[station.pk] = station_thread
            station_thread.start()
            sleep(3)
            return station_thread

    @classmethod
    def remove(cls, station_id):
        """Remove StationThread associated with *station*

        This also shuts down the thread
        """
        with cls.__lock:
            station_thread = cls.__station_threads.pop(station_id)
            station_thread.stop()

    @classmethod
    def get(cls, station):
        """Return the StationThread associated with station

        Return None if no thread is associated with that station
        """
        return cls.__station_threads.get(station.pk)

    @classmethod
    def get_all(cls):
        """Return a dict of all station threads."""
        return cls.__station_threads.copy()

    def run(self):
        LOGGER.debug('Starting %s', self.name)
        self.mpc.create_config().start()
        self.mooder.start()
        self.running = True
        self.dj_ango = Player.dj_ango()

        while self.running:
            playlist = self.mpc.call('playlist')
            current_song = self.mpc.currently_playing()

            self.previous_song = current_song

            if len(playlist) > 1:
                LOGGER.debug('%s: Waiting for playlist to change', self.name)
                self.mpc.call('idle', 'playlist')
                continue

            if (len(playlist) == 1
                and (current_song['remaining_time']
                     > self.secs_to_inject_new_song)):
                secs = (current_song['remaining_time']
                        - self.secs_to_inject_new_song)
                LOGGER.debug('%s: Waiting %s seconds', self.name, secs)
                SocketHandler.notify_clients(current_song=current_song)
                if self.scrobble:
                    scrobble_song(current_song, True)
                self.mpc.idle_or_wait(secs)

            if self.scrobble:
                scrobble_song(current_song, False)

            artist = self.mpc.get_last_artist(playlist)
            artist = None if artist == 'TeamPlayer' else artist
            players = self.station.participants()
            entry = songs.find_a_song(
                players,
                self.station,
                self.previous_player,
                artist,
            )

            if entry is None:
                LOGGER.info('%s: No players with any queued titles', self.name)
                QUEUE_CHANGE_EVENT.wait()
                continue

            self.previous_player = entry.queue.player
            song = entry.song
            try:
                new_filename = copy_entry_to_queue(entry, self.mpc)
            except (IOError, shutil.Error):
                LOGGER.error('IOError copying %s.', song.name, exc_info=True)
                entry.delete()
                continue

            if not self.mpc.wait_for_song(new_filename):
                entry.delete()
                continue

            LOGGER.info(
                u"%s: Adding %s's %s",
                self.name,
                self.previous_player,
                entry
            )
            self.mpc.add_file_to_playlist(new_filename)
            entry_dict = EntrySerializer(entry).data
            entry.delete()
            SocketHandler.message(entry.queue.player, 'song_removed',
                                  entry_dict)

            # log "mood"
            if entry.queue.player != self.dj_ango:
                self.mooder.queue.put(entry.artist)

            # delete files not in playlist
            self.mpc.purge_queue_dir()

    def stop(self):
        LOGGER.critical('%s Shutting down' % self.name)
        self.mpc.stop()
        self.mooder.stop()
        self.running = False


class SocketServer(threading.Thread):
    """
    Tornado web server in a thread.

    This server will handle WebSocket requests
    """
    def run(self):
        LOGGER.debug('%s has started', self.name)
        self.application = tornado.web.Application([
            (r"/", SocketHandler),
            (r"/ipc", IPCHandler),
        ])
        self.application.listen(settings.WEBSOCKET_PORT)

        tornado.ioloop.IOLoop.instance().start()

    @staticmethod
    def shutdown():
        LOGGER.critical('Shutting down.')
        tornado.ioloop.IOLoop.current().stop()

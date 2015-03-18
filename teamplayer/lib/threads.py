"""Thread classes and helpers for TeamPlayer."""
import logging
import shutil
import threading

import tornado.gen
import tornado.web

from teamplayer.conf import settings
from teamplayer.lib import copy_entry_to_queue, signals, songs
from teamplayer.lib.mpc import MPC
from teamplayer.lib.websocket import IPCHandler, SocketHandler
from teamplayer.models import Mood, Player, Station
from teamplayer.serializers import EntrySerializer

LOGGER = logging.getLogger('teamplayer.threads')


@tornado.gen.coroutine
def scrobble_song(song, now_playing=False):
    """Signal handler to scrobble when a song changes."""
    # only the Main Station scrobbles
    if song and song['artist'] != 'DJ Ango':
        LOGGER.debug('Scrobbling “%s” by %s', song['title'], song['artist'])
        songs.scrobble_song(song, now_playing=now_playing)


@tornado.gen.coroutine
def log_mood(artist, station):
    """Record the mood for the given artist and station"""
    if artist == 'Unknown':
        return
    LOGGER.debug('Logging mood for %s', artist)
    Mood.log_mood(artist, station)


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

        self.running = False
        self.mpc = MPC(self.station)
        self.mpc.create_config().start()
        self.scrobble = (settings.SCROBBLER_USER
                         and self.station == Station.main_station())
        self.previous_player = None
        self.previous_song = None

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

    def wait_for(self, song):
        """Let clients and scrobbler know the song is playing and wait to end"""
        SocketHandler.notify_clients(current_song=song)

        if self.scrobble:
            scrobble_song(song, True)

        secs = song['remaining_time'] - self.secs_to_inject_new_song
        secs = max(0, secs)
        LOGGER.debug('%s: Waiting %s seconds', self.name, secs)
        self.mpc.idle_or_wait(secs)

        if self.scrobble:
            scrobble_song(song, False)

    def run(self):
        LOGGER.debug('Starting %s', self.name)
        self.running = True
        self.dj_ango = Player.dj_ango()

        while self.running:
            playlist = self.mpc.call('playlist')
            len_playlist = len(playlist)
            current_song = self.mpc.currently_playing()

            self.previous_song = current_song

            if len_playlist > 1:
                # Looks like we already added the next song
                LOGGER.debug('%s: Waiting for playlist to change', self.name)
                self.mpc.call('idle', 'playlist')
                continue

            if len_playlist == 1:
                signals.song_start.send(
                    Station,
                    player=self.previous_player,
                    song_info=current_song
                )
                self.wait_for(current_song)
                signals.song_end.send(
                    Station,
                    player=self.previous_player,
                    song_info=current_song
                )

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
                signals.QUEUE_CHANGE_EVENT.wait()
                continue

            self.previous_player = entry.queue.player
            song = entry.song
            try:
                filename = copy_entry_to_queue(entry, self.mpc)
            except (IOError, shutil.Error):
                LOGGER.error('IOError copying %s.', song.name, exc_info=True)
                entry.delete()
                continue

            if not self.mpc.wait_for_song(filename):
                entry.delete()
                continue

            msg = "%s: Adding %s's %s"
            LOGGER.info(msg, self.name, self.previous_player, entry)
            self.mpc.add_file_to_playlist(filename)
            entry_dict = EntrySerializer(entry).data
            entry.delete()
            SocketHandler.message(entry.queue.player, 'song_removed',
                                  entry_dict)

            # log "mood"
            if entry.queue.player != self.dj_ango:
                log_mood(entry.artist, self.station)

            # delete files not in playlist
            self.mpc.purge_queue_dir()

    def stop(self):
        LOGGER.critical('%s Shutting down' % self.name)
        self.mpc.stop()
        self.running = False


def start_socket_server():
    """Start the tornado event loop"""
    LOGGER.debug('Tornado has started')
    application = tornado.web.Application([
        (r"/", SocketHandler),
        (r"/ipc", IPCHandler),
    ])
    application.listen(settings.WEBSOCKET_PORT)

    tornado.ioloop.IOLoop.instance().start()

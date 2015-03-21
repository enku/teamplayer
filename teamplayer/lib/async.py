"""Asynchronous threads and coroutines for TeamPlayer."""
import logging
import shutil
import threading

import mpd

from teamplayer.conf import settings
from teamplayer.lib import copy_entry_to_queue, signals, songs
from teamplayer.lib.mpc import MPC
from teamplayer.lib.websocket import SocketHandler
from teamplayer.models import Mood, Player, Station
from teamplayer.serializers import EntrySerializer

LOGGER = logging.getLogger('teamplayer.async')


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
        self.mpc.create_config()
        self.mpc.start()
        self.previous_player = None
        self.event_thread = EventThread(mpc=self.mpc)

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
        secs = song['remaining_time'] - self.secs_to_inject_new_song
        secs = max(0, secs)
        LOGGER.debug('%s: Waiting %s seconds', self.name, secs)
        self.mpc.idle_or_wait(secs)

    @classmethod
    def purge_queue_dir(cls, **kwargs):
        station = kwargs.get('sender')

        if not station:
            return

        station_thread = cls.get(station)
        if not station_thread:
            return

        station_thread.mpc.purge_queue_dir()

    def run(self):
        LOGGER.debug('Starting %s', self.name)
        self.running = True
        self.dj_ango = Player.dj_ango()

        self.event_thread.start()
        while not self.event_thread.running:
            pass

        while self.running:
            playlist = self.mpc.call('playlist')
            len_playlist = len(playlist)
            current_song = self.mpc.currently_playing()

            if len_playlist > 1:
                # Looks like we already added the next song
                LOGGER.debug('%s: Waiting for playlist to change', self.name)
                self.mpc.call('idle', 'playlist')
                continue

            if len_playlist == 1:
                self.wait_for(current_song)

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

    def stop(self):
        self.running = False

        LOGGER.critical('%s Shutting down' % self.name)
        self.event_thread.stop()
        self.mpc.stop()


class EventThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        self.mpc = kwargs.pop('mpc')
        self.running = False

        super().__init__(*args, **kwargs)

    def run(self):
        previous_song = None
        self.running = True

        while self.running:
            try:
                self.mpc.call('idle', 'player')
            except mpd.ConnectionError:
                # the station went away and so will we
                self.stop()
                return

            current_song = self.mpc.currently_playing()
            signals.song_change.send(
                self.mpc.station,
                station_id=self.mpc.station_id,
                previous_song=previous_song,
                current_song=current_song
            )

            previous_song = current_song

    def stop(self):
        self.running = False


###################
# Signal Handlers #
###################
def scrobble_song(sender, **kwargs):
    """Signal handler to scrobble when a song changes."""
    station = sender
    previous_song = kwargs['previous_song']
    current_song = kwargs['current_song']

    # only the Main Station scrobbles
    if station != Station.main_station():
        return

    if previous_song and previous_song['title'] != 'Station Break':
        songs.scrobble_song(previous_song, now_playing=False)

    if current_song and current_song['title'] != 'Station Break':
        songs.scrobble_song(current_song, now_playing=True)


def log_mood(sender, **kwargs):
    """Record the mood for the current artist on the given station"""
    station = sender
    mpc = StationThread.get(station).mpc
    song_info = mpc.call('currentsong')

    if not song_info:
        return

    if song_info['artist'] in ('Unknown', 'DJ Ango'):
        return

    player = Player.objects.from_filename(song_info['file'])
    if player == Player.dj_ango():
        return

    LOGGER.debug('Logging %s\'s mood for %s' % (player, song_info['artist']))
    Mood.log_mood(song_info['artist'], station)


# Signal connections
signals.song_change.connect(SocketHandler.notify_clients)
signals.song_change.connect(log_mood)
signals.song_change.connect(StationThread.purge_queue_dir)
if settings.SCROBBLER_USER:
    signals.song_change.connect(scrobble_song)

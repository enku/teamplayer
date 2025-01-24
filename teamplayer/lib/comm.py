"""Asynchronous threads and handlers TeamPlayer."""

from __future__ import annotations

import threading
from typing import Any

import mpd

from teamplayer import logger
from teamplayer.conf import settings
from teamplayer.lib import now, signals, songs
from teamplayer.lib.mpc import MPC, CurrentlyPlaying
from teamplayer.lib.websocket import SocketHandler
from teamplayer.models import Mood, Player, PlayLog, Station
from teamplayer.serializers import EntrySerializer


class StationThread(threading.Thread):
    """Class to handle stations, starting/stopping their mpds
    and the creation/removal process.
    """

    __station_threads: dict[int, "StationThread"] = {}
    __lock = threading.Lock()

    secs_to_inject_new_song = settings.CROSSFADE + 1.5

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.station = kwargs.pop("station")
        super(StationThread, self).__init__(*args, **kwargs)

        self.running = False
        self.mpc = MPC(self.station)
        self.mpc.create_config()
        self.mpc.start()
        self.event_thread = EventThread(mpc=self.mpc)

    @classmethod
    def create(cls: type["StationThread"], station: Station) -> "StationThread":
        """Create and return a StationThread.

        If the StationThread associated with station already exists, simply
        return that thread.
        """
        with cls.__lock:
            if station.pk in cls.__station_threads:
                return cls.__station_threads[station.pk]

            station_thread = StationThread(
                name=f"Station {station.pk}", station=station
            )
            cls.__station_threads[station.pk] = station_thread
            station_thread.start()
            return station_thread

    @classmethod
    def remove(cls, station_id: int) -> None:
        """Remove StationThread associated with *station*

        This also shuts down the thread
        """
        with cls.__lock:
            station_thread = cls.__station_threads.pop(station_id)
            station_thread.stop()

    @classmethod
    def get(cls, station: Station) -> "StationThread" | None:
        """Return the StationThread associated with station

        Return None if no thread is associated with that station
        """
        return cls.__station_threads.get(station.pk)

    @classmethod
    def get_all(cls) -> dict[int, "StationThread"]:
        """Return a dict of all station threads."""
        return cls.__station_threads.copy()

    def wait_for(self, song: CurrentlyPlaying) -> None:
        """Wait for **song** to end."""
        secs = song["remaining_time"] - self.secs_to_inject_new_song
        secs = max(0, secs)
        logger.debug("%s: Waiting %s seconds", self.name, secs)
        self.mpc.idle_or_wait(secs)

    @classmethod
    def purge_queue_dir(cls, **kwargs: Any) -> None:
        station = kwargs.get("sender")

        if not station:
            return

        station_thread = cls.get(station)
        if not station_thread:
            return

        station_thread.mpc.purge_queue_dir()

    def run(self) -> None:
        try:
            self.run_forever()
        except Exception:
            logger.exception(f"Station {self.station.id}: Error inside main loop")
            logger.error(f"Current song: {self.mpc.currently_playing()}")

            raise

    def run_forever(self) -> None:
        logger.debug("Starting %s", self.name)
        self.running = True
        self.dj_ango = Player.dj_ango()
        player = None

        self.event_thread.start()
        while not self.event_thread.running:
            pass

        while self.running:
            playlist = self.mpc.call("playlist")
            len_playlist = len(playlist)
            current_song = self.mpc.currently_playing()

            if len_playlist > 1:
                # Looks like we already added the next song
                logger.debug("%s: Waiting for playlist to change", self.name)
                self.mpc.call("idle", "playlist")
                continue

            if len_playlist == 1:
                self.wait_for(current_song)

            artist = self.mpc.get_last_artist(playlist)
            artist = None if artist == "TeamPlayer" else artist
            players = self.station.participants()
            entry = songs.find_a_song(players, self.station, player, artist)

            if entry is None:
                logger.info("%s: No players with any queued titles", self.name)
                signals.QUEUE_CHANGE_EVENT.wait()
                continue

            player = entry.queue.player
            logger.info("%s: Adding %s's %s", self.name, player, entry)
            self.mpc.add_entry_to_playlist(entry)
            entry_dict = EntrySerializer(entry).data
            entry.delete()
            SocketHandler.message(player, "song_removed", entry_dict)

    def stop(self) -> None:
        self.running = False

        logger.critical("%s Shutting down" % self.name)
        self.event_thread.stop()
        self.mpc.stop()


class EventThread(threading.Thread):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.mpc = kwargs.pop("mpc")
        self.running = False

        super().__init__(*args, **kwargs)

    def run(self) -> None:
        previous_song = None
        self.running = True

        while self.running:
            try:
                self.mpc.call("idle", "player")
            except mpd.ConnectionError:
                # the station went away and so will we
                self.stop()
                return

            current_song = self.mpc.currently_playing(stickers=["dj", "player_id"])
            results = signals.song_change.send_robust(
                self.mpc.station,
                station_id=self.mpc.station_id,
                previous_song=previous_song,
                current_song=current_song,
            )
            for receiver, response in results:
                if isinstance(response, Exception):
                    msg = "Exception raise in signal handler"
                    logger.debug(msg, exc_info=response)

            previous_song = current_song

    def stop(self) -> None:
        self.running = False


###################
# Signal Handlers #
###################
def scrobble_song(sender: Station, **kwargs: Any) -> None:
    """Signal handler to scrobble when a song changes."""
    station = sender
    previous_song = kwargs["previous_song"]
    current_song = kwargs["current_song"]

    # only the Main Station scrobbles
    if station != Station.main_station():
        return

    if previous_song and previous_song["title"] and previous_song["artist"]:
        songs.scrobble_song(previous_song, now_playing=False)

    if current_song and current_song["title"] and current_song["artist"]:
        songs.scrobble_song(current_song, now_playing=True)


def log_mood(sender: Station, **kwargs: Any) -> None:
    """Record the mood for the current artist on the given station"""
    station = sender
    song_info = kwargs["current_song"]

    if not song_info:
        return

    if song_info["artist"] in ("Unknown", "", None):
        return

    player = Player.objects.get(pk=song_info["player_id"])
    if player == Player.dj_ango():
        return

    logger.debug("Logging %s's mood for %s" % (player, song_info["artist"]))
    Mood.log_mood(song_info["artist"], station)


def play_log(sender: Station, **kwargs: Any) -> PlayLog | None:
    """Log the current song being played"""
    station = sender
    song_info = kwargs["current_song"]

    if not song_info:
        return None

    artist = song_info["artist"]
    if artist in ("Unknown", "", None):
        return None

    player = Player.objects.get(pk=song_info["player_id"])
    title = song_info["title"]
    time = now()
    playlog = PlayLog.objects.create(
        artist=artist, player=player, station=station, time=time, title=title
    )

    logger.debug("%s", playlog)

    return playlog


# Signal connections
signals.song_change.connect(SocketHandler.notify_clients)
signals.song_change.connect(log_mood)
signals.song_change.connect(play_log)
signals.song_change.connect(StationThread.purge_queue_dir)
if settings.SCROBBLER_USER:
    signals.song_change.connect(scrobble_song)

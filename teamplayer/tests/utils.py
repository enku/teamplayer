"""Utilities for TeamPlayer unit tests"""
import os
import threading
from io import StringIO
from unittest.mock import patch

import django.core.files.uploadedfile

import teamplayer.lib
import teamplayer.models

Entry = teamplayer.models.Entry
UploadedFile = django.core.files.uploadedfile.UploadedFile

DIR = os.path.dirname(__file__)
SILENCE = os.path.join(DIR, "data", "silence.mp3")


def getdata(filename, flags="r"):
    fullpath = os.path.join(DIR, "data", filename)
    return open(fullpath, flags)


class SpinDoctor:

    """Emulate the spin management command

    This does not include:
        * scrobbling
        * logging
    """

    def __init__(self):
        self.previous_player = teamplayer.models.Player.active_players().order_by(
            "user__username"
        )[0]
        self.silence = ("DJ Ango", "TeamPlayer", "Station Break", 15, 0)
        self.current_song = self.previous_song = self.silence
        self.current_player = None
        self.station = teamplayer.models.Station.main_station()

    def next(self, similar_artists=None):
        """Emulate one interation of the spin management command loop"""
        similar_artists = similar_artists or []
        self.current_song = self.previous_song
        players = teamplayer.models.Player.active_players()

        if self.previous_song[1] != "TeamPlayer":
            artist = self.previous_song[1]
        else:
            artist = None

        entry = teamplayer.lib.songs.find_a_song(
            players, self.station, self.previous_player, artist
        )

        if entry is None:
            self.current_song = self.silence
            self.current_player = None

            return self.current_song

        self.previous_player = entry.queue.player
        entry.delete()

        # log "mood"
        with patch("teamplayer.models.lib.songs.get_similar_artists") as gsa:
            gsa.return_value = similar_artists
            threading.Thread(
                target=teamplayer.models.Mood.log_mood,
                args=(entry.artist, self.station),
            ).run()

        player = self.previous_player
        self.current_song = (player.dj_name, entry.artist, entry.title, 15, 0)
        self.current_player = player
        return self.current_song

    def create_song_for(self, player, title, artist):
        """Emulate adding a song in a player's queue"""
        queue = player.queue
        entry = Entry()
        entry.station = self.station
        entry.queue = queue
        entry.artist = artist
        entry.title = title
        entry.filetype = "MP3"
        entry.song.save(
            teamplayer.lib.get_random_filename(), UploadedFile(StringIO(""))
        )
        entry.save()
        return entry

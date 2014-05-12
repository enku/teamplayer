"""Utilities for TeamPlayer unit tests"""
from io import StringIO
import os
import threading

import django.core.files.uploadedfile

import teamplayer.models
import teamplayer.lib

Entry = teamplayer.models.Entry
UploadedFile = django.core.files.uploadedfile.UploadedFile

__dir__ = os.path.dirname(__file__)
ARTIST_XML = os.path.join(__dir__, 'data', 'prince_artistinfo.xml')
PRINCE_SIMILAR_TXT = os.path.join(__dir__, 'data', 'prince_similar.txt')
METALLICA_SIMILAR_TXT = os.path.join(__dir__, 'data', 'metallica_similar.txt')
SILENCE = os.path.join(__dir__, 'data', 'silence.mp3')


class SpinDoctor:

    """Emulate the spin management command

    This does not include:
        * scrobbling
        * logging
    """
    def __init__(self):
        self.previous_player = teamplayer.models.Player.active_players()\
            .order_by('user__username')[0]
        self.silence = ('DJ Ango', 'TeamPlayer', 'Station Break', 15, 0)
        self.current_song = self.previous_song = self.silence
        self.current_player = None
        self.station = teamplayer.models.Station.main_station()

    def next(self):
        """Emulate one interation of the spin management command loop"""
        self.current_song = self.previous_song
        players = teamplayer.models.Player.active_players()
        if self.previous_song[1] != 'TeamPlayer':
            artist = self.previous_song[1]
        else:
            artist = None

        entry = teamplayer.lib.songs.find_a_song(
            players,
            self.station,
            self.previous_player,
            artist
        )
        if entry is None:
            self.current_song = self.silence
            self.current_player = None
            return self.current_song
        self.previous_player = entry.queue.player
        entry.delete()

        # log "mood"
        threading.Thread(
            target=teamplayer.models.Mood.log_mood,
            args=(entry.artist, self.station)
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
        entry.filetype = 'MP3'
        entry.song.save(
            teamplayer.lib.get_random_filename(),
            UploadedFile(StringIO(''))
        )
        entry.save()
        return entry

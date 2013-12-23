"""Utilities for TeamPlayer unit tests"""
import cStringIO
import os
import threading

import django.core.files.uploadedfile
import django.contrib.auth.models

import teamplayer.models
import teamplayer.lib

Entry = teamplayer.models.Entry
StringIO = cStringIO.StringIO
UploadedFile = django.core.files.uploadedfile.UploadedFile
User = django.contrib.auth.models.User

__dir__ = os.path.dirname(__file__)
ARTIST_XML = os.path.join(__dir__, 'data', 'prince_artistinfo.xml')
SILENCE = os.path.join(__dir__, 'data', 'silence.mp3')


class SpinDoctor:

    """Emulate the spin management command

    This does not include:
        * scrobbling
        * logging
    """
    def __init__(self):
        self.previous_user = User.active_users().order_by('username')[0]
        self.silence = ('DJ Ango', 'TeamPlayer', 'Station Break', 15, 0)
        self.current_song = self.previous_song = self.silence
        self.current_user = None
        self.station = teamplayer.models.Station.main_station()

    def next(self):
        """Emulate one interation of the spin management command loop"""
        self.current_song = self.previous_song
        users = User.active_users()
        if self.previous_song[1] != 'TeamPlayer':
            artist = self.previous_song[1]
        else:
            artist = None

        entry = teamplayer.lib.songs.find_a_song(
            users,
            self.station,
            self.previous_user,
            artist
        )
        if entry is None:
            self.current_song = self.silence
            self.current_user = None
            return self.current_song
        self.previous_user = entry.queue.userprofile.user
        entry.delete()

        # log "mood"
        threading.Thread(
            target=teamplayer.lib.songs.log_mood,
            args=(entry.artist, self.station)
        ).run()
        user = self.previous_user
        self.current_song = (user.userprofile.dj_name, entry.artist,
                             entry.title, 15, 0)
        self.current_user = user
        return self.current_song

    def create_song_for(self, user, title, artist):
        """Emulate adding a song in a user's queue"""
        queue = user.userprofile.queue
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

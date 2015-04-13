"""
Functions for interacting with mpc/mpd
"""
import contextlib
import os
import shutil
import subprocess
from threading import Event, Thread
from time import sleep, time

import mpd
from django.conf import settings as django_settings
from django.core.urlresolvers import reverse

from teamplayer import logger
from teamplayer.conf import settings
from teamplayer.lib import songs

MPD_UPDATE_MAX = 20  # seconds
MPD_UPDATE_WAIT = 0.5  # seconds


class MPC(object):
    """Interface to a mpc client."""
    def __init__(self, station):
        join = os.path.join
        self.mpd_dir = join(settings.MPD_HOME, str(station.pk))
        self.mpd = None
        self.station = station
        self.station_id = station.id
        self.address = settings.MPD_ADDRESS
        self.port = self.station_id + settings.MPD_PORT
        self.http_port = self.station_id + settings.HTTP_PORT
        self.conf_file = join(self.mpd_dir, 'mpd.conf')
        self.pid_file = join(self.mpd_dir, 'mpd.pid')
        self.db_file = join(self.mpd_dir, 'mpd.db')
        self.sticker_file = join(self.mpd_dir, 'mpd.stickers')
        self.queue_dir = join(self.mpd_dir, 'queue')

        if not os.path.exists(self.mpd_dir):
            os.makedirs(self.mpd_dir)

        if not os.path.exists(self.queue_dir):
            os.makedirs(self.queue_dir)

    def start(self):
        """
        Start the mpd deamon.  Insert a file and play
        """
        assert self.mpd is None
        self.mpd = subprocess.Popen(('mpd', '--no-daemon', self.conf_file))

        # this is terrible. basically we want to block until mpd is listening
        while True:
            try:
                self.call('status')
            except ConnectionRefusedError:  # NOQA
                continue
            break

        self.call('update')
        self.call('consume', 1)
        self.call('play')

    def stop(self):
        """
        Stop the mpd daemon.
        """
        if self.mpd:
            self.mpd.terminate()
        self.mpd = None

        if os.path.exists(self.mpd_dir):
            try:
                shutil.rmtree(self.mpd_dir)
            except FileNotFoundError:  # NOQA
                pass

    def create_config(self):
        """Create the mpd config file and write the config to it"""
        mpd_file = open(self.conf_file, 'w')
        context = {
            'ADDRESS': self.address,
            'DB_FILE': self.db_file,
            'STICKER_FILE': self.sticker_file,
            'HTTP_PORT': self.http_port,
            'MPD_LOG': settings.MPD_LOG,
            'MAX_OUTPUT_BUFFER_SIZE': settings.MAX_OUTPUT_BUFFER_SIZE,
            'MPD_MAX_CONNECTIONS': settings.MPD_MAX_CONNECTIONS,
            'PID_FILE': self.pid_file,
            'PORT': self.port,
            'QUEUE_DIR': self.queue_dir,
            'STREAM_BITRATE': settings.STREAM_BITRATE,
            'STREAM_FORMAT': settings.STREAM_FORMAT,
            'ZEROCONF_NAME': 'TeamPlayer Station #%s' % self.station.pk
        }

        mpd_file.write("""# Automatically generated.  Do not edit.

    port                    "{PORT}"
    bind_to_address         "{ADDRESS}"
    music_directory         "{QUEUE_DIR}"
    pid_file                "{PID_FILE}"
    db_file                 "{DB_FILE}"
    sticker_file            "{STICKER_FILE}"
    log_file                "{MPD_LOG}"
    max_connections         "{MPD_MAX_CONNECTIONS}"
    max_output_buffer_size  "{MAX_OUTPUT_BUFFER_SIZE}"
    zeroconf_name           "{ZEROCONF_NAME}"

    audio_output {{
        enabled             "yes"
        always_on           "yes"
        type                "httpd"
        name                "TeamPlayer HTTP Stream"
        encoder             "lame"
        port                "{HTTP_PORT}"
        bitrate             "{STREAM_BITRATE}"
        format              "{STREAM_FORMAT}"
    }}
    """.format(**context))

        # make sure the config queue dir exists
        if not os.path.isdir(settings.QUEUE_DIR):
            os.makedirs(settings.QUEUE_DIR)
        return self

    def currently_playing(self, stickers=None):
        """Return a dict representing the currently playing song

        The structure of the dict is as follows::

            {
                'artist': 'Spoon',
                'title': 'New York Kiss',
                'dj': 'DJ Scratch',
                'total_time': 207,
                'remaining_time': 46,
                'station_id': 1,
                'artist_image': '/artist/Spoon/image',
            }

        If the station is currently silent (station break) then "artist" and
        "title" will be `None`.  Similarly "total_time" and "remaining_time"
        will be `0`.

        If `stickers` is given, also provide the values for the keys listed in
        `stickers`.
        """
        not_playing = {
            'artist': None,
            'title': None,
            'dj': 'DJ Ango',
            'total_time': 0,
            'remaining_time': 0,
            'station_id': self.station_id,
            'artist_image': songs.CLEAR_IMAGE_URL
        }
        current_song = self.call('currentsong')

        if stickers is None:
            stickers = ['dj']

        if not current_song:
            return not_playing

        status = self.call('status')

        try:
            time_str = status['time']
        except KeyError:
            return not_playing

        elapsed_time, total_time = (int(i) for i in time_str.split(':'))
        filename = current_song['file']
        artist = current_song.get('artist', None)
        title = current_song.get('title', None)

        if artist:
            artist_image = reverse(
                'teamplayer.views.artist_image', kwargs={'artist': artist})
        else:
            artist_image = songs.CLEAR_IMAGE_URL

        data = {
            'artist': artist,
            'title': title,
            'total_time': total_time,
            'remaining_time': total_time - elapsed_time,
            'station_id': self.station_id,
            'artist_image': artist_image
        }

        song_stickers = self.call('sticker_list', 'song', filename)
        for sticker in stickers:
            data[sticker] = song_stickers.get(sticker, None)

        return data

    def add_entry_to_playlist(self, entry):
        """Add `entry` to the mpd playlist"""
        assert entry.station == self.station

        try:
            filename = self.copy_entry_to_queue(entry)
        except (IOError, shutil.Error):
            logger.exception('IOError copying %s.', entry.song.name)
            return None

        if not self.wait_for_song(filename):
            if os.path.exists(filename):
                os.unlink(filename)
            return None

        self.call('add', filename)

        # add some stickers
        player = entry.queue.player
        try:
            self.call('sticker_set', 'song', filename, 'player_id', player.pk)
            self.call('sticker_set', 'song', filename, 'dj', player.dj_name)
        except mpd.CommandError:
            # It appears sometimes we can get an error writing the sticker.
            # This is not critical but, of course, we lose metadata on read
            pass

        if settings.CROSSFADE:
            self.call('crossfade', settings.CROSSFADE)
        self.call('play')
        return filename

    def copy_entry_to_queue(self, entry):
        """
        Given Entry entry, copy it to the mpc queue directory as efficiently as
        possible.
        """
        song = entry.song
        player = entry.queue.player
        filename = os.path.join(django_settings.MEDIA_ROOT, song.name)
        basename = os.path.basename(filename)

        new_filename = '{0}-{1}'.format(player.pk, basename)
        logger.debug('copying to %s', new_filename)

        new_path = os.path.join(self.queue_dir, new_filename)

        # First we try to make a hard link for efficiency
        try:
            if os.path.exists(new_path):
                os.unlink(new_path)
            os.link(filename, new_path)
        except OSError:
            shutil.copy(filename, new_path)

        return new_filename

    @contextlib.contextmanager
    def connect(self):
        """Connect to the mpd deamon"""
        client = mpd.MPDClient()
        try:
            client.connect(self.address, self.port)
            yield client
        finally:
            try:
                client.disconnect()
            except mpd.ConnectionError:
                pass

    def call(self, command, *args):
        """
        Connect to mpd and call args
        """
        with self.connect() as conn:
            func = getattr(conn, command)
            return func(*args)

    def wait_for_song(self, filename):
        """
        Wait for the song to show up in the mpd listing
        within the time frame.  If the song shows up return True, else
        return False
        """
        # wait for it to show up
        try_until_time = int(time()) + MPD_UPDATE_MAX
        while True:
            self.call('update')
            files = [i['file'] for i in self.call('listall')
                     if 'file' in i]
            if filename in files:
                return True
            elif time() > try_until_time:
                # we maxed out our wait time
                logger.error('%s never made it to the playlist', filename)
                return False
            sleep(MPD_UPDATE_WAIT)

    def purge_queue_dir(self):
        """Remove "used" files form mpd's queue_dir"""
        files = [i['file'] for i in self.call('listall') if 'file' in i]
        playlist = [i[6:] for i in self.call('playlist')
                    if i.startswith('file: ')]
        for mpd_file in files:
            if mpd_file not in playlist:
                os.remove(os.path.join(self.queue_dir, mpd_file))
        self.call('update')

    def get_last_artist(self, playlist):
        """
        Return the artist of the last item in the mpd playlist
        or None if the playlist is empty
        """
        if playlist:
            basename = playlist[-1]
            if basename.startswith('file: '):
                basename = basename[6:]
            filename = os.path.join(self.queue_dir, basename)
            return songs.get_song_metadata(filename)['artist']
        return None

    def idle_or_wait(self, secs):
        """
        Return after secs seconds or when playlist changes state, whichever
        comes first.
        """
        idle_done = Event()

        def set_idle_done_event():
            self.call('idle', 'playlist')
            idle_done.set()

        Thread(target=set_idle_done_event).start()
        return idle_done.wait(secs)

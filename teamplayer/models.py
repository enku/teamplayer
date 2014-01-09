"""
ORM models for the TeamPlayer app
"""
import datetime
import logging
import os
import random
import uuid

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.files import File
from django.db import models, transaction

from . import lib
from . conf import settings

DJ_ANGO = None
LOGGER = logging.getLogger('teamplayer.models')


class Queue(models.Model):

    """A user's queue containing song entries"""
    objects = models.Manager()
    active = models.BooleanField(default=True)

    def __str__(self):
        return "%s's Queue" % self.player.username

    def add_song(self, song_file, station):
        """Add <<song_file>> to queue"""

        # get the extension of the original filename
        dot = song_file.name.rfind('.')
        if dot != -1:
            extension = song_file.name[dot + 1:]
        else:
            extension = None

        filename = lib.get_random_filename(extension)

        # create entry
        entry = Entry(queue=self, station=station)
        entry.song.save(filename, song_file)

        try:
            metadata = lib.songs.get_song_metadata(entry.song.path)
            artist, title, filetype = metadata
        except lib.songs.SongMetadataError:
            entry.song.delete()
            entry.delete()
            raise
        entry.artist = artist
        entry.title = title
        entry.filetype = filetype
        entry.save()
        return entry

    @transaction.commit_on_success
    def randomize(self, station):
        """Randomize entries in the queue """
        for entry in self.entry_set.filter(station=station):
            entry.place = random.randint(0, 256)
            entry.save()
        return

    @transaction.commit_on_success
    def reorder(self, id_list):
        """Reorder entries in queue accoring to entry.ids in id_list"""
        for order, i in enumerate(reversed(id_list)):
            try:
                entry = Entry.objects.get(pk=i)
            except Entry.DoesNotExist:
                continue

            if entry not in self.entry_set.all():
                continue
            entry.place = order
            entry.save()

        return self.entry_set.values('id', 'artist', 'title')

    @transaction.commit_on_success
    def order_by_rank(self, station):
        """Set the each Entry's .place field by it's artist rank"""
        for entry in self.entry_set.filter(station=station):
            entry.place = entry.artist_mood(station)
            entry.save()

    def toggle_status(self):
        self.active = not self.active
        self.save()
        return self.active

    @property
    def user(self):
        return self.player.user

    def auto_fill(self, max_entries, station=None, qs_filter=None, minimum=0):
        """
        Fill the queue up to max_entries from the Library.

        If ``station`` is not provided it defaults to the "Main Station".

        ``qs_fitler`` is a dict to apply to SongFile.objects.filter().
        If not provided it defaults to {}

        Note this is intented to only be used for the "DJ Ango" queue
        though it's not enforced in the code.
        """
        # to avoid circular imports
        from tp_library.models import SongFile

        qs_filter = qs_filter or {}

        station = station or Station.main_station()
        entries = Entry.objects.filter(queue=self, station=station)
        entries_count = entries.count()
        if entries.count() > minimum:
            return
        entries_needed = max_entries - entries_count

        song_files = SongFile.objects.filter(**qs_filter)

        if settings.AUTOFILL_STRATEGY == 'contiguous':
            song_files = self.auto_fill_contiguous(song_files, entries_needed)
        else:
            song_files = self.auto_fill_random(song_files, entries_needed)

        for songfile in song_files:
            logging.debug(songfile)
            try:
                fp = File(open(songfile.filename, 'rb'))
                self.add_song(fp, station)
            except Exception:
                LOGGER.error('auto_fill exception: SongFile(%s)',
                             songfile.pk,
                             exc_info=True)

    # TODO: Unit test
    @staticmethod
    def auto_fill_random(queryset, entries_needed):
        """Return at most *entries_needed* SongFiles from the *queryset*.

        The songs are randomly scattered among the *queryset*
        """
        song_files = set()
        song_count = queryset.count()
        if not song_count:
            return song_files

        num_to_get = min(song_count, entries_needed)
        while len(song_files) < num_to_get:
            song_file = queryset[random.randint(0, song_count - 1)]
            song_files.add(song_file)
        return song_files

    # TODO: Unit test
    @staticmethod
    def auto_fill_contiguous(queryset, entries_needed):
        """Return at most *entries_needed* SongFiles from the *queryset*.

        The songs are selected randomly but are contiguous among the *queryset*
        """
        song_count = queryset.count()
        if not song_count:
            return set()
        min_first_song = max(0, song_count - entries_needed)
        first_song_idx = random.randint(0, min_first_song)
        song_files = queryset[first_song_idx:first_song_idx + entries_needed]
        return set(song_files)


class Entry(models.Model):

    """A song entry pointing to a file on the filesystem"""
    objects = models.Manager()
    queue = models.ForeignKey(Queue)
    station = models.ForeignKey('Station', related_name='entries')
    place = models.IntegerField(default=0)
    song = models.FileField(upload_to='songs')
    title = models.CharField(default='Unknown', max_length=254)
    artist = models.CharField('Unknown', max_length=254)
    filetype = models.CharField(max_length=4, blank=False)

    def __str__(self):
        return u'“%s” by %s' % (self.title, self.artist)

    def delete(self, *args, **kwargs):
        if self.song:
            filename = os.path.join(django_settings.MEDIA_ROOT, self.song.name)
            try:
                os.unlink(filename)
            except OSError:
                pass
        super(Entry, self).delete(*args, **kwargs)

    def artist_mood(self, station):
        """
        Return the artist's Mood.count for this artist
        """
        qs = Mood.objects.filter(
            artist=self.artist,
            station=station,
            timestamp__gt=lib.now() - datetime.timedelta(hours=24)
        )
        return qs.count()

    class Meta:
        """ORM metadata"""
        ordering = ('-place', 'id')


class Mood(models.Model):

    """Artists that TeamPlayer "likes" (have been played)"""
    objects = models.Manager()
    station = models.ForeignKey('Station')
    artist = models.TextField()
    timestamp = models.DateTimeField(auto_now=True, auto_now_add=True)

    def __str__(self):
        return u'%s: %s' % (self.artist, self.date)

    class Meta:
        ordering = ('-timestamp', 'artist')


class Station(models.Model):
    __main_station = None

    objects = models.Manager()
    name = models.CharField(max_length=128, unique=True)
    creator = models.ForeignKey(User, unique=True)

    def __str__(self):
        return self.name

    def get_songs(self):
        """Return queryset of all (active) songs in the station"""
        return Entry.objects.filter(
            station=self,
            queue__active=True,
        )

    @classmethod
    def get_stations(cls):
        return cls.objects.all().order_by('pk')

    def current_song(self):
        return lib.mpc.MPC(station=self).currently_playing()

    def url(self, request):
        try:
            http_host = request.META.get('HTTP_HOST', 'localhost')
        except AttributeError:
            http_host = request.host

        if ':' in http_host:
            http_host = http_host.split(':', 1)[0]

        mpc = lib.mpc.MPC(station=self)
        return 'http://{0}:{1}/mpd.mp3'.format(
            http_host,
            mpc.http_port,
        )

    @classmethod
    def from_user(cls, user):
        """Return the station belong to user or None if user has no station"""
        try:
            return cls.objects.get(creator=user)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_station(cls, station_name, creator):
        station = cls()
        station.name = station_name
        station.creator = creator
        station.full_clean()
        station.save()
        return station

    @classmethod
    def main_station(cls):
        if not cls.__main_station:
            cls.__main_station = cls.objects.get(name=u'Main Station')
        return cls.__main_station


class AuthToken(models.Model):

    """XMLRPC Authentication token"""

    life_span = datetime.timedelta(seconds=1800)
    timestamp = models.DateTimeField()
    string = models.CharField(max_length=36, unique=True)

    def save(self, *args, **kwargs):
        self.timestamp = datetime.datetime.now()
        if not self.string:
            self.string = str(uuid.uuid4(), encoding='ascii')
        return super(AuthToken, self).save(*args, **kwargs)

    def is_valid(self):
        """Return True iff the token is still valid"""
        return datetime.datetime.now() - self.timestamp <= self.life_span

    def __str__(self):
        return self.string


class Player(models.Model):

    """Player: misc. data assocated with a User"""
    objects = models.Manager()
    user = models.OneToOneField(User, unique=True, related_name='player')
    queue = models.OneToOneField(Queue)
    auth_token = models.OneToOneField(AuthToken, null=True, blank=True)
    dj_name = models.CharField(blank=True, max_length=25)
    auto_mode = models.BooleanField(default=False)

    def toggle_auto_mode(self):
        """Toggle the user's auto_mode. Return new mode."""
        self.auto_mode = not self.auto_mode
        self.save()
        return self.auto_mode

    def set_dj_name(self, name):
        self.dj_name = name
        self.full_clean()
        self.save()
        return self.dj_name

    @property
    def username(self):
        return self.user.username

    @classmethod
    def user_stats(cls):
        """Return a dictionary of user stats (all users)"""
        active_queues = Queue.objects.filter(
            active=True).values_list('pk', flat=True)
        songs_in_queue = Entry.objects.filter(
            queue__pk__in=active_queues,
        )

        return {
            'active_queues': len(active_queues),
            'songs': len(songs_in_queue),
            'stations': Station.get_stations().count(),
        }


@classmethod
def dj_ango(cls):
    global DJ_ANGO
    if DJ_ANGO:
        return DJ_ANGO

    DJ_ANGO = User.objects.get(username='DJ Ango')
    return DJ_ANGO
User.add_to_class('dj_ango', dj_ango)


@classmethod
def active_users(cls):
    players = Player.objects.values_list('user__pk', flat=True)
    return cls.objects.filter(is_active=True,
                              pk__in=players)
User.add_to_class('active_users', active_users)

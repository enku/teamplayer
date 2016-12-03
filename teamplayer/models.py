"""
ORM models for the TeamPlayer app
"""
import datetime
import logging
import os
import random

import pkg_resources

from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models, transaction

from . import lib, logger
from .conf import settings
from .lib import signals

DJ_ANGO = None


class Queue(models.Model):

    """A player's queue containing song entries"""
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
        except lib.songs.SongMetadataError:
            entry.song.delete()
            entry.delete()
            raise
        entry.artist = metadata['artist']
        entry.title = metadata['title']
        entry.filetype = metadata['type']
        entry.save()
        return entry

    def randomize(self, station):
        """Randomize entries in the queue """
        entries = self.entry_set.filter(station=station)
        entry_count = entries.count()

        if not entry_count:
            return

        place_list = list(range(entry_count))
        random.shuffle(place_list)

        with transaction.atomic():
            for entry, place in zip(entries, place_list):
                entry.place = place
                entry.save()

    @transaction.atomic
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

    @transaction.atomic
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

        ``qs_fitler`` is a dict to apply to LibraryItem.objects.filter().
        If not provided it defaults to {}

        Note this is intented to only be used for the "DJ Ango" queue
        though it's not enforced in the code.
        """
        # to avoid circular imports
        from teamplayer.lib.autofill import auto_fill_from_tags

        qs_filter = qs_filter or {}

        station = station or Station.main_station()
        station = Station.objects.get(pk=station.pk)  # re-fetch
        entries = Entry.objects.filter(queue=self, station=station)
        entries_count = entries.count()
        if entries.count() > minimum:
            return
        entries_needed = max_entries - entries_count

        song_files = LibraryItem.objects.filter(**qs_filter)

        if station != Station.main_station():
            if '#' not in station.name:
                return

            logger.debug('Station name has a #. Filling based on tags')
            strategy = auto_fill_from_tags
        else:
            strategy_name = settings.AUTOFILL_STRATEGY
            iter_ = pkg_resources.iter_entry_points(
                'teamplayer.autofill_strategy',
                strategy_name,
            )
            strategy = next(iter_).load()

        song_files = strategy(
            entries_needed=entries_needed,
            queryset=song_files,
            station=station,
        )

        for songfile in song_files:
            logging.debug(songfile)
            try:
                fp = File(open(songfile.filename, 'rb'))
                self.add_song(fp, station)
            except Exception:
                logger.error('auto_fill exception: LibraryItem(%s)',
                             songfile.pk,
                             exc_info=True)
        if song_files:
            signals.QUEUE_CHANGE_EVENT.set()
            signals.QUEUE_CHANGE_EVENT.clear()


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
        return '“%s” by %s' % (self.title, self.artist)

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
            artist__iexact=self.artist,
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
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s: %s' % (self.artist, self.timestamp)

    class Meta:
        ordering = ('-timestamp', 'artist')

    @classmethod
    def log_mood(cls, artist, station):
        """Log the artist and similar artists in the Mood database"""
        cls.objects.create(
            artist=artist,
            station=station
        )

        similar_artists = lib.songs.get_similar_artists(artist)
        for artist in similar_artists:
            cls.objects.create(
                artist=artist,
                station=station,
            )


class StationManager(models.Manager):

    def get_queryset(self):
        """Override default queryset to only return enabled stations"""
        return super(StationManager, self).get_queryset().filter(enabled=True)

    @property
    def disabled(self):
        """Return queryset for all disabled stations"""
        return super(StationManager, self).get_queryset().filter(enabled=False)

    def create_station(self, **kwargs):
        songs = kwargs.pop('songs', [])
        creator = kwargs.pop('creator')

        qs = super(StationManager, self).get_queryset()
        station, _ = qs.get_or_create(creator=creator)
        for name, value in kwargs.items():
            setattr(station, name, value)
        station.enabled = True
        station.full_clean()
        station.save()

        queue = station.creator.queue
        for songfile in songs:
            with open(songfile.filename, 'rb') as fp:
                django_file = File(fp)
                queue.add_song(django_file, station)

        return station


class Station(models.Model):
    __main_station = None

    objects = StationManager()
    name = models.CharField(max_length=128, unique=True)
    creator = models.OneToOneField('Player')
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_songs(self):
        """Return queryset of all (active) songs in the station"""
        return Entry.objects.filter(
            station=self,
            queue__active=True,
        )

    def participants(self):
        """Return the set of Users with songs ready for this station."""
        entries_qs = Entry.objects.filter(
            station=self,
            queue__active=True
        )
        return Player.objects.filter(
            queue__entry__in=entries_qs,
        ).distinct()

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
    def from_player(cls, player):
        """Return the player's station or None if player has no station"""
        try:
            return cls.objects.get(creator=player)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_station(cls, station_name, creator):
        return cls.objects.create_station(name=station_name, creator=creator)

    @classmethod
    def main_station(cls):
        if not cls.__main_station:
            cls.__main_station = cls.objects.get(name='Main Station')
        return cls.__main_station


class PlayerManager(models.Manager):

    def create_player(self, username, **kwargs):
        """Create a player with username"""
        user_kwargs = {'username': username}
        password = kwargs.pop('password', None)

        if password is not None:
            user_kwargs['password'] = password

        user = User.objects.create_user(**user_kwargs)
        queue = Queue.objects.create()

        player = Player.objects.create(
            user=user,
            queue=queue,
            dj_name=''
        )
        return player


class Player(models.Model):

    """Player: misc. data assocated with a User"""
    objects = PlayerManager()
    user = models.OneToOneField(User, unique=True, related_name='player')
    queue = models.OneToOneField(Queue)
    dj_name = models.CharField(blank=True, max_length=25)
    auto_mode = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

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
    def player_stats(cls):
        """Return a dictionary of player stats (all players)"""
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

        DJ_ANGO = cls.objects.get(user__username='DJ Ango')
        return DJ_ANGO

    @classmethod
    def active_players(cls):
        return cls.objects.filter(user__is_active=True)


class LibraryItem(models.Model):
    objects = models.Manager()

    filename = models.TextField(unique=True)
    filesize = models.IntegerField()
    mimetype = models.TextField()
    artist = models.TextField()
    title = models.TextField()
    album = models.TextField()
    length = models.IntegerField(null=True)  # in seconds
    genre = models.TextField(null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    station_id = models.IntegerField()
    added_by = models.ForeignKey(Player, related_name='library_songs')

    class Meta:
        unique_together = (('artist', 'title', 'album'),)

    def similar_artists(self):
        return (lib.songs.get_similar_artists(self.artist)
                if self.artist
                else None)

    def exists(self):
        return os.path.exists(self.filename)

    @classmethod
    def metadata_get_or_create(cls, filename, metadata, contributer, st_id):
        try:
            artist = lib.first_or_none(metadata, 'artist') or ''
            title = lib.first_or_none(metadata, 'title') or ''
            album = lib.first_or_none(metadata, 'album') or ''
            genre = lib.first_or_none(metadata, 'genre') or None
            length = metadata.info.length

            if length:
                length = int(length)
            else:
                length = None

        except Exception as error:
            logger.error('Error getting metadata for %s: %s', filename, error)
            raise

        # see if we already have a file with said metadata
        try:
            return (cls.objects.get(artist__iexact=artist,
                                    title__iexact=title,
                                    album__iexact=album),
                    False)
        except cls.DoesNotExist:
            pass

        songfile = cls(
            filename=filename,
            filesize=os.stat(filename).st_size,
            mimetype=metadata.mime[0],
            artist=artist,
            title=title,
            album=album,
            length=length,
            genre=genre,
            station_id=st_id,
            added_by=contributer
        )
        songfile.full_clean()  # callers should trap me
        songfile.save()

        return (songfile, True)

    def image(self):
        """Return artist image url"""
        return lib.songs.get_image_url_for(self.artist)

    def __str__(self):
        if self.title:
            return '"{0}" by {1}'.format(self.title, self.artist)
        return self.filename

    def clean(self):
        if self.artist.lower() in ('', 'unknown'):
            raise ValidationError('Invalid artist: %s' % self.artist)

        self.genre = self.genre or None
        self.length = self.length or None

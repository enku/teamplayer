"""
ORM models for the TeamPlayer app
"""

from __future__ import annotations

import datetime
import functools
import importlib.metadata
import logging
import os
import random
from typing import Any

import django.http
import mutagen.mp3
import tornado.httputil
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models, transaction
from typing_extensions import NotRequired, TypedDict

from teamplayer import lib, logger
from teamplayer.conf import settings
from teamplayer.lib import signals

User = get_user_model()


class EntryDict(TypedDict):
    id: int
    artist: str
    title: str


class PlayerStats(TypedDict):
    active_queues: int
    songs: int
    stations: int
    users: NotRequired[int]


class Queue(models.Model):
    """A player's queue containing song entries"""

    objects = models.Manager()
    active = models.BooleanField(default=True)
    player: Player

    def __str__(self) -> str:
        return f"{self.player.username}'s Queue"

    def add_song(self, song_file: File[bytes], station: Station) -> Entry:
        """Add <<song_file>> to queue"""
        assert song_file.name

        # get the extension of the original filename
        dot = song_file.name.rfind(".")
        if dot != -1:
            extension = song_file.name[dot + 1 :]
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
        entry.artist = metadata["artist"]
        entry.title = metadata["title"]
        entry.album = metadata["album"]
        entry.filetype = metadata["type"]
        entry.save()
        return entry

    def randomize(self, station: Station) -> None:
        """Randomize entries in the queue"""
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
    def reorder(self, id_list: list[int]) -> list[EntryDict]:
        """Reorder entries in queue according to entry.ids in id_list"""
        for order, i in enumerate(reversed(id_list)):
            try:
                entry = Entry.objects.get(pk=i)
            except Entry.DoesNotExist:
                continue

            if entry not in self.entry_set.all():
                continue
            entry.place = order
            entry.save()

        return list(self.entry_set.values("id", "artist", "title"))

    @transaction.atomic
    def order_by_rank(self, station: Station) -> None:
        """Set the each Entry's .place field by it's artist rank"""
        for entry in self.entry_set.filter(station=station):
            entry.place = entry.artist_mood(station)
            entry.save()

    def toggle_status(self) -> bool:
        self.active = not self.active
        self.save()
        return self.active

    @property
    def user(self) -> "django.contrib.auth.models.AbstractUser":
        return self.player.user

    def auto_fill(
        self,
        max_entries: int,
        station: Station | None = None,
        qs_filter: dict[str, Any] | None = None,
        minimum: int = 0,
    ) -> None:
        """
        Fill the queue up to max_entries from the Library.

        If ``station`` is not provided it defaults to the "Main Station".

        ``qs_filter`` is a dict to apply to LibraryItem.objects.filter().
        If not provided it defaults to {}

        Note this is intended to only be used for the "DJ Ango" queue
        though it's not enforced in the code.
        """
        # to avoid circular imports
        # pylint: disable=import-outside-toplevel
        from teamplayer.lib.autofill import auto_fill_from_tags

        qs_filter = qs_filter or {}

        station = station or Station.main_station()
        station = Station.objects.get(pk=station.pk)  # re-fetch
        entries = Entry.objects.filter(queue=self, station=station)
        if entries.count() > minimum:
            return

        if station != Station.main_station():
            assert station
            if "#" not in station.name:
                return

            logger.debug("Station name has a #. Filling based on tags")
            strategy = auto_fill_from_tags
        else:
            strategy_name = settings.AUTOFILL_STRATEGY
            [entry_point] = importlib.metadata.entry_points(
                group="teamplayer.autofill_strategy",
                name=strategy_name,
            )
            strategy = entry_point.load()

        song_files = strategy(
            entries_needed=max_entries - entries.count(),
            queryset=LibraryItem.objects.filter(**qs_filter),
            station=station,
        )

        for songfile in song_files:
            logging.debug(songfile)
            try:
                with open(songfile.filename, "rb") as fp:
                    model_file = File(fp)
                    self.add_song(model_file, station)
            # I think originally this was set to be broad because we don't know what
            # kinds of exceptions mutagen is going to raise. TODO: capture mutagen
            # errors where it is called and raise a custom exception that we can catch
            # here.
            # pylint: disable=broad-exception-caught
            except Exception:
                logger.exception("auto_fill exception: LibraryItem(%s)", songfile.pk)
        if song_files:
            signals.QUEUE_CHANGE_EVENT.set()
            signals.QUEUE_CHANGE_EVENT.clear()


class Entry(models.Model):
    """A song entry pointing to a file on the filesystem"""

    objects = models.Manager()
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE)
    station = models.ForeignKey(
        "Station",
        on_delete=models.CASCADE,
        related_name="entries",
    )
    place = models.IntegerField(default=0)
    song = models.FileField(upload_to="songs")
    title = models.CharField(default="Unknown", max_length=254)
    artist = models.CharField("Unknown", max_length=254)
    album = models.CharField(max_length=254, null=True)
    filetype = models.CharField(max_length=4, blank=False)

    def __str__(self) -> str:
        return f"“[self.title]” by {self.artist}"

    def delete(
        self, using: Any = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.song:
            filename = os.path.join(django_settings.MEDIA_ROOT, self.song.name)
            try:
                os.unlink(filename)
            except OSError:
                pass
        return super().delete(using=using, keep_parents=keep_parents)

    def artist_mood(self, station: Station) -> int:
        """
        Return the artist's Mood.count for this artist
        """
        qs = Mood.objects.filter(
            artist__iexact=self.artist,
            station=station,
            timestamp__gt=lib.now() - datetime.timedelta(hours=24),
        )
        return qs.count()

    class Meta:
        """ORM metadata"""

        ordering = ("-place", "id")


class Mood(models.Model):
    """Artists that TeamPlayer "likes" (have been played)"""

    objects = models.Manager()
    station = models.ForeignKey("Station", on_delete=models.CASCADE)
    artist = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.artist}: {self.timestamp}"

    class Meta:
        ordering = ("-timestamp", "artist")

    @classmethod
    def log_mood(cls, artist: str, station: Station) -> None:
        """Log the artist and similar artists in the Mood database"""
        cls.objects.create(artist=artist, station=station)

        similar_artists = lib.songs.get_similar_artists(artist)
        for artist in similar_artists:
            cls.objects.create(
                artist=artist,
                station=station,
            )


class StationManager(models.Manager["Station"]):
    def get_queryset(self) -> models.QuerySet[Station]:
        """Override default queryset to only return enabled stations"""
        return super().get_queryset().filter(enabled=True)

    @property
    def disabled(self) -> models.QuerySet[Station]:
        """Return queryset for all disabled stations"""
        return super().get_queryset().filter(enabled=False)

    def create_station(self, **kwargs: Any) -> Station:
        songs = kwargs.pop("songs", [])
        creator = kwargs.pop("creator")

        qs = super().get_queryset()
        station, _ = qs.get_or_create(creator=creator)
        for name, value in kwargs.items():
            setattr(station, name, value)
        station.enabled = True
        station.full_clean()
        station.save()

        queue = station.creator.queue
        for songfile in songs:
            with open(songfile.filename, "rb") as fp:
                django_file = File(fp)
                queue.add_song(django_file, station)

        return station


class Station(models.Model):
    __main_station: Station | None = None

    objects = StationManager()
    name = models.CharField(max_length=128, unique=True)
    creator = models.OneToOneField("Player", on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name

    def get_songs(self) -> models.QuerySet[Entry]:
        """Return queryset of all (active) songs in the station"""
        return Entry.objects.filter(
            station=self,
            queue__active=True,
        )

    def participants(self) -> models.QuerySet[Player]:
        """Return the set of Users with songs ready for this station."""
        entries_qs = Entry.objects.filter(station=self, queue__active=True)
        return Player.objects.filter(
            queue__entry__in=entries_qs,
        ).distinct()

    @classmethod
    def get_stations(cls) -> models.QuerySet[Station]:
        return cls.objects.all().order_by("pk")

    def current_song(self) -> lib.mpc.CurrentlyPlaying:
        from teamplayer.lib import mpc as libmpc

        return libmpc.MPC(station=self).currently_playing()

    def url(
        self, request: django.http.HttpRequest | tornado.httputil.HTTPServerRequest
    ) -> str:
        from teamplayer.lib import mpc as libmpc

        http_host = (
            request.host
            if isinstance(request, tornado.httputil.HTTPServerRequest)
            else request.META.get("HTTP_HOST", "localhost")
        )

        if ":" in http_host:
            http_host = http_host.split(":", 1)[0]

        mpc = libmpc.MPC(station=self)
        return f"http://{http_host}:{mpc.http_port}/mpd.mp3"

    @classmethod
    def from_player(cls, player: Player) -> Station | None:
        """Return the player's station or None if player has no station"""
        try:
            return cls.objects.get(creator=player)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_station(cls, station_name: str, creator: Player) -> Station:
        return cls.objects.create_station(name=station_name, creator=creator)

    @classmethod
    def main_station(cls) -> Station:
        if not cls.__main_station:
            cls.__main_station = cls.objects.get(name="Main Station")
        return cls.__main_station


class PlayerManager(models.Manager["Player"]):
    def create_player(self, username: str, **kwargs: Any) -> Player:
        """Create a player with username"""
        user_kwargs = {"username": username}
        password = kwargs.pop("password", None)

        if password is not None:
            user_kwargs["password"] = password

        user = User.objects.create_user(**user_kwargs)
        queue = Queue.objects.create()

        player = Player.objects.create(user=user, queue=queue, dj_name="")
        return player


class Player(models.Model):
    """Player: misc. data associated with a User"""

    objects = PlayerManager()
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        unique=True,
        related_name="player",
    )
    queue = models.OneToOneField(Queue, on_delete=models.CASCADE)
    dj_name = models.CharField(blank=True, max_length=25)
    auto_mode = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.user.username

    def toggle_auto_mode(self) -> bool:
        """Toggle the user's auto_mode. Return new mode."""
        self.auto_mode = not self.auto_mode
        self.save()
        return self.auto_mode

    def set_dj_name(self, name: str) -> str:
        self.dj_name = name
        self.full_clean()
        self.save()
        return self.dj_name

    @property
    def username(self) -> str:
        return self.user.username

    @classmethod
    def player_stats(cls) -> PlayerStats:
        """Return a dictionary of player stats (all players)"""
        active_queues = Queue.objects.filter(active=True).values_list("pk", flat=True)
        songs_in_queue = Entry.objects.filter(
            queue__pk__in=active_queues,
        )

        return {
            "active_queues": len(active_queues),
            "songs": len(songs_in_queue),
            "stations": Station.get_stations().count(),
        }

    @classmethod
    @functools.cache
    def dj_ango(cls) -> Player:
        return cls.objects.get(user__username="DJ Ango")

    @classmethod
    def active_players(cls) -> models.QuerySet[Player]:
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
    added_by = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="library_songs",
    )

    class Meta:
        unique_together = (("artist", "title", "album"),)

    def similar_artists(self) -> list[str] | None:
        return lib.songs.get_similar_artists(self.artist) if self.artist else None

    def exists(self) -> bool:
        return os.path.exists(self.filename)

    @classmethod
    def metadata_get_or_create(
        cls,
        filename: str,
        metadata: mutagen.mp3.EasyMP3,
        contributor: Player,
        st_id: int,
    ) -> tuple[LibraryItem, bool]:
        try:
            artist = lib.first_or_none(metadata, "artist") or ""
            title = lib.first_or_none(metadata, "title") or ""
            album = lib.first_or_none(metadata, "album") or ""
            genre = lib.first_or_none(metadata, "genre") or None

            assert metadata.info
            length = metadata.info.length

        except Exception as error:
            logger.error("Error getting metadata for %s: %s", filename, error)
            raise

        # see if we already have a file with said metadata
        try:
            return (
                cls.objects.get(
                    artist__iexact=artist, title__iexact=title, album__iexact=album
                ),
                False,
            )
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
            added_by=contributor,
        )
        songfile.full_clean()  # callers should trap me
        songfile.save()

        return (songfile, True)

    def image(self) -> str:
        """Return artist image url"""
        return lib.songs.get_image_url_for(self.artist)

    def __str__(self) -> str:
        if self.title:
            return f'"{self.title}" by {self.artist}'
        return self.filename

    def clean(self) -> None:
        if self.artist.lower() in ("", "unknown"):
            raise ValidationError(f"Invalid artist: {self.artist}")

        self.genre = self.genre or None
        self.length = self.length or None


class PlayLog(models.Model):
    """A log of songs played"""

    station = models.ForeignKey(
        Station,
        on_delete=models.CASCADE,
        db_index=True,
    )
    title = models.CharField(max_length=254)
    artist = models.CharField(max_length=254)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["station", "time"]]

    def __str__(self) -> str:
        return (
            f"|{self.time}|Station {self.station.pk}: “{self.title}” by {self.artist}"
        )

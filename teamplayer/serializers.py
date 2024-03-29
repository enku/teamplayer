from __future__ import annotations

from django.urls import reverse
from rest_framework import serializers

from teamplayer import models
from teamplayer.lib import mpc


class EntrySerializer(serializers.ModelSerializer[models.Entry]):
    url = serializers.SerializerMethodField()

    class Meta:
        model = models.Entry
        fields = ("id", "artist", "title", "station", "url")
        order_by = "place"

    def get_url(self, obj: models.Entry) -> str:
        return reverse("show_entry", args=(obj.pk,))


class StationSerializer(serializers.ModelSerializer[models.Station]):
    creator: serializers.SlugRelatedField[models.Player] = serializers.SlugRelatedField(
        read_only=True, slug_field="username"
    )

    songs = serializers.SerializerMethodField("get_song_count")
    current_song = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    stream = serializers.SerializerMethodField()

    class Meta:
        model = models.Station
        fields = ("id", "name", "creator", "songs", "current_song", "url", "stream")
        order_by = "id"

    def get_song_count(self, obj: models.Station) -> int:
        return obj.get_songs().count()

    def get_stream(self, obj: models.Station) -> str:
        return obj.url(self.context["request"])

    def get_url(self, obj: models.Station) -> str:
        return reverse("station", args=(obj.pk,))

    def get_current_song(self, obj: models.Station) -> mpc.CurrentlyPlaying:
        return obj.current_song()


class PlayerSerializer(serializers.ModelSerializer[models.Player]):
    username = serializers.SerializerMethodField()
    entries = serializers.SerializerMethodField("get_entry_count")
    paused = serializers.SerializerMethodField("get_hold_state")

    class Meta:
        model = models.Player
        fields = ("username", "auto_mode", "paused", "entries")

    def get_username(self, obj: models.Player) -> str:
        return obj.user.username

    def get_entry_count(self, obj: models.Player) -> int:
        return obj.queue.entry_set.count()

    def get_hold_state(self, obj: models.Player) -> bool:
        return not obj.queue.active

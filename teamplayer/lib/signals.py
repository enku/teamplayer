"""Django Signals and threading Events for the TeamPlayer app."""

from threading import Event

from django.dispatch import Signal

QUEUE_CHANGE_EVENT = Event()

song_change = Signal()
library_add = Signal()
station_create = Signal()
station_delete = Signal()
song_added = Signal()
song_removed = Signal()

"""Django Signals and threading Events for the TeamPlayer app."""
from threading import Event

from django.dispatch import Signal

QUEUE_CHANGE_EVENT = Event()

song_start = Signal(providing_args=('player', 'song_info'))

library_add = Signal(providing_args=('player', 'song_info', 'path'))

station_create = Signal(providing_args=('station_id',))
station_delete = Signal(providing_args=('station_id',))

song_added = Signal(providing_args=('song_id',))
song_removed = Signal(providing_args=('song_id',))

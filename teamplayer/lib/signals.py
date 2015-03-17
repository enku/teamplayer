"""Django Signals and threading Events for the TeamPlayer app."""
from threading import Event

from django.dispatch import Signal

QUEUE_CHANGE_EVENT = Event()

song_change = Signal(providing_args=('player', 'song_info'))

library_add = Signal(providing_args=('player', 'song_info', 'path'))

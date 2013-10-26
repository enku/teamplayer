"""Django Signals and threading Events for the TeamPlayer app."""
from threading import Event

from django.dispatch import Signal

SONG_CHANGE = Signal(providing_args=['station_id',
                                     'previous_song',
                                     'current_song'])

QUEUE_CHANGE_EVENT = Event()

"""
App-specific settings defaults for the TeamPlayer app
"""
import os

from django.conf import settings as django_settings

from teamplayer import __path__

PATH = __path__[0]

USER_SETTINGS = getattr(django_settings, "TEAMPLAYER", None)

DEFAULTS = {
    "MPD_HOME": PATH,
    "QUEUE_DIR": None,
    "MPD_ADDRESS": "localhost",
    "MPD_PORT": 6600,
    "MPD_LOG": "/dev/null",
    "MPD_DB": None,
    "HTTP_PORT": 8000,  # Channels will alway be 1 + this, so don't worry
    "WEBSOCKET_PORT": 8000,
    "STREAM_QUALITY": 8.0,
    "STREAM_BITRATE": 64,
    "STREAM_FORMAT": "44100:16:2",
    "MPD_MAX_CONNECTIONS": 30,
    "MAX_OUTPUT_BUFFER_SIZE": 16384,
    "REPO_URL": None,
    "SCROBBLER_USER": "",
    "SCROBBLER_PASSWORD": "",
    "LASTFM_APIKEY": "2d5952c801e074e3251bafb77f54e680",
    "LASTFM_APISECRET": "23dd84f772d374d7f8230d74afc8d269",
    "CROSSFADE": 0,
    "SHAKE_THINGS_UP": 0,
    "SHAKE_THINGS_UP_FILTER": {"length__lt": 300, "length__gt": 0},
    "ALWAYS_SHAKE_THINGS_UP": False,
    "AUTOFILL_STRATEGY": "random",
    "AUTOFILL_MOOD_HISTORY": 3600,
    "AUTOFILL_MOOD_TOP_ARTISTS": 50,
    "UPLOADED_LIBRARY_DIR": "",
}


class TeamPlayerSettings(object):
    def __init__(self, user_settings=None, defaults=None):
        self.user_settings = user_settings or {}
        self.defaults = defaults or {}

    def __getattr__(self, attr):
        if attr not in self.defaults.keys():
            raise AttributeError()

        try:
            val = self.user_settings[attr]
        except KeyError:
            val = self.defaults[attr]

        val = self.validate_setting(attr, val)
        setattr(self, attr, val)
        return val

    def validate_setting(self, attr, val):
        if attr == "QUEUE_DIR" and not val:
            return os.path.join(self.MPD_HOME, "queue")

        if attr == "MPD_DB" and not val:
            return os.path.join(self.MPD_HOME, "mpd.db")

        return val


settings = TeamPlayerSettings(USER_SETTINGS, DEFAULTS)
del PATH

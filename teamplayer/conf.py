"""
App-specific settings defaults for the TeamPlayer app
"""
import json
import os

from strtobool import strtobool

from teamplayer import __path__

PATH = __path__[0]

DEFAULTS = {
    "MPD_HOME": PATH,
    "QUEUE_DIR": "",
    "MPD_ADDRESS": "localhost",
    "MPD_PORT": 6600,
    "MPD_LOG": "/dev/null",
    "MPD_DB": "",
    "HTTP_PORT": "8000",  # Channels will alway be 1 + this, so don't worry
    "WEBSOCKET_PORT": "8000",
    "STREAM_QUALITY": "8.0",
    "STREAM_BITRATE": "64",
    "STREAM_FORMAT": "44100:16:2",
    "MPD_MAX_CONNECTIONS": "30",
    "MAX_OUTPUT_BUFFER_SIZE": "16384",
    "REPO_URL": "",
    "SCROBBLER_USER": "",
    "SCROBBLER_PASSWORD": "",
    "LASTFM_APIKEY": "2d5952c801e074e3251bafb77f54e680",
    "LASTFM_APISECRET": "23dd84f772d374d7f8230d74afc8d269",
    "CROSSFADE": "0",
    "SHAKE_THINGS_UP": "0",
    "SHAKE_THINGS_UP_FILTER": '{"length__lt": 300, "length__gt": 0}',
    "ALWAYS_SHAKE_THINGS_UP": False,
    "AUTOFILL_STRATEGY": "random",
    "AUTOFILL_MOOD_HISTORY": "3600",
    "AUTOFILL_MOOD_TOP_ARTISTS": "50",
    "UPLOADED_LIBRARY_DIR": "",
    "SPOTIFY_CLIENT_ID": "80c76cbf28ef4a24afda36a8b3ede7be",
    "SPOTIFY_CLIENT_SECRET": "67a7221fdf884aabb23f5d61969da609",
}


class TeamPlayerSettings(object):
    def __init__(self, prefix=None, defaults=None):
        self.prefix = prefix
        self.defaults = defaults or {}

    def __getattr__(self, attr):
        if attr not in self.defaults.keys():
            raise AttributeError()

        try:
            value = os.environ[f"{self.prefix}{attr}"]
        except KeyError:
            value = self.defaults[attr]

        value = self.validate_setting(attr, value)
        setattr(self, attr, value)

        return value

    def validate_setting(self, attr, value):
        if attr in [
            "AUTOFILL_MOOD_HISTORY",
            "AUTOFILL_MOOD_TOP_ARTISTS",
            "CROSSFADE",
            "HTTP_PORT",
            "MAX_OUTPUT_BUFFER",
            "MPD_MAX_CONNECTIONS",
            "MPD_PORT",
            "SHAKE_THINGS_UP",
            "STREAM_BITRATE",
            "WEBSOCKET_PORT",
        ]:
            return int(value)

        if attr in ["STREAM_QUALITY"]:
            return float(value)

        if attr in ["SHAKE_THINGS_UP_FILTER"]:
            return json.loads(value)

        if attr in ["ALWAYS_SHAKE_THINGS_UP"]:
            return strtobool(value)

        if attr == "QUEUE_DIR" and not value:
            return os.path.join(self.MPD_HOME, "queue")

        if attr == "MPD_DB" and not value:
            return os.path.join(self.MPD_HOME, "mpd.db")

        return value


settings = TeamPlayerSettings("TEAMPLAYER_", DEFAULTS)

del PATH

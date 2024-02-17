"""
App-specific settings defaults for the TeamPlayer app
"""

import builtins
import json
import os
from dataclasses import dataclass, fields
from typing import Any, Mapping

from strtobool import strtobool

from teamplayer import __path__ as my_path


@dataclass
class TeamPlayerSettings:

    MPD_HOME: str = my_path[0]
    QUEUE_DIR: str = ""
    MPD_ADDRESS: str = "localhost"
    MPD_PORT: int = 6600
    MPD_LOG: str = "/dev/null"
    MPD_DB: str = ""
    HTTP_PORT: int = 8000  # Channels will always be 1 + this, so don't worry
    WEBSOCKET_PORT: int = 8000
    STREAM_QUALITY: float = 8.0
    STREAM_BITRATE: int = 64
    STREAM_FORMAT: str = "44100:16:2"
    MPD_MAX_CONNECTIONS: int = 30
    MAX_OUTPUT_BUFFER_SIZE: int = 16384
    REPO_URL: str = ""
    SCROBBLER_USER: str = ""
    SCROBBLER_PASSWORD: str = ""
    LASTFM_APIKEY: str = "2d5952c801e074e3251bafb77f54e680"
    LASTFM_APISECRET: str = "23dd84f772d374d7f8230d74afc8d269"
    CROSSFADE: float = 0.0
    SHAKE_THINGS_UP: int = 0
    SHAKE_THINGS_UP_FILTER: str = '{"length__lt": 300, "length__gt": 0}'
    ALWAYS_SHAKE_THINGS_UP: bool = False
    AUTOFILL_STRATEGY: str = "random"
    AUTOFILL_MOOD_HISTORY: int = 3600
    AUTOFILL_MOOD_TOP_ARTISTS: int = 50
    UPLOADED_LIBRARY_DIR: str = ""
    SPOTIFY_CLIENT_ID: str = "80c76cbf28ef4a24afda36a8b3ede7be"
    SPOTIFY_CLIENT_SECRET: str = "67a7221fdf884aabb23f5d61969da609"

    @classmethod
    def from_dict(cls, prefix: str, mapping: Mapping[str, str]):
        params: dict[str, Any] = {}

        for field in fields(cls):
            if (key := f"{prefix}{field.name}") not in mapping:
                continue

            match field.type:
                case builtins.bool:
                    value = strtobool(mapping[key])
                case builtins.int:
                    value = int(mapping[key])
                case builtins.float:
                    value = float(mapping[key])
                case _:
                    value = mapping[key]

            params[field.name] = value

        return cls(**params)

    @classmethod
    def from_environ(
        cls, *, prefix: str | None = None, env: Mapping[str, str] = os.environ
    ):
        if prefix is None:
            prefix = "TEAMPLAYER_"

        return cls.from_dict(prefix, env)

    def __post_init__(self) -> None:
        if not self.QUEUE_DIR:
            self.QUEUE_DIR = os.path.join(self.MPD_HOME, "queue")

        if not self.MPD_HOME:
            self.MPD_HOME = os.path.join(self.MPD_HOME, "mpd.db")

        self.SHAKE_THINGS_UP_FILTER = json.loads(self.SHAKE_THINGS_UP_FILTER)


settings = TeamPlayerSettings.from_environ(prefix="TEAMPLAYER_")

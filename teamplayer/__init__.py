"""
Welcome to TeamPlayer: The Democratic Internet Radio Station
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger("teamplayer")


class TeamPlayerConfig(AppConfig):
    name = "teamplayer"
    label = "teamplayer"
    verbose_name = "TeamPlayer"


default_app_config = "teamplayer.TeamPlayerConfig"

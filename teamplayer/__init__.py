"""
Welcome to TeamPlayer: The Democratic Internet Radio Station
"""
import logging
import os
import subprocess

try:
    from django.apps import AppConfig
except ImportError:
    AppConfig = object


VERSION = (2, 6, 1, "final")
REVISION = None

logger = logging.getLogger("teamplayer")


def version_string(version=VERSION, show_revision=True):
    """Return *version* as a string.

    If inside a git repo and "git" is available, also append the revision hash.
    """
    global REVISION

    if show_revision and REVISION is None:
        dirname = os.path.dirname(__file__)
        with open(os.devnull, "w") as devnull:
            try:
                popen = subprocess.Popen(
                    ["git", "-C", dirname, "rev-parse", "--short", "HEAD"],
                    stdout=subprocess.PIPE,
                    stderr=devnull,
                )
                if popen.wait() == 0:
                    REVISION = popen.stdout.read().decode("ascii").strip()
            except OSError:
                REVISION = ""

    string = ".".join(str(i) for i in version[:3])

    if version[3] != "final":
        string = f"{string}-{version[3]}"

    if REVISION:
        string = f"{string} ({REVISION})"

    return string


class TeamPlayerConfig(AppConfig):
    name = "teamplayer"
    label = "teamplayer"
    verbose_name = "TeamPlayer"


default_app_config = "teamplayer.TeamPlayerConfig"

"""
Welcome to TeamPlayer: The Democratic Internet Radio Station
"""
import os
import subprocess

VERSION = (2, 2, 0, 'final')
REVISION = None


def version_string(version=VERSION, show_revision=True):
    """Return *version* as a string.

    If inside a mercurial repo and "hg" is available, also append the revision
    hash.
    """
    global REVISION

    if show_revision and REVISION is None:
        dirname = os.path.dirname(__file__)
        try:
            popen = subprocess.Popen(
                ['hg', 'id', '-i', '--cwd', dirname],
                stdout=subprocess.PIPE,
                stderr=open(os.devnull, 'w')
            )
            if popen.wait() == 0:
                REVISION = popen.stdout.read().decode('ascii').strip()
        except OSError:
            REVISION = ''

    string = '.'.join(str(i) for i in version[:3])

    if version[3] != 'final':
        string = '{0}-{1}'.format(string, version[3])

    if REVISION:
        string = '{0} ({1})'.format(string, REVISION)

    return string

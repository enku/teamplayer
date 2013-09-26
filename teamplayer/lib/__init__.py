"""TeamPlayer Library package"""
import datetime
import logging
import os
import shutil
import tempfile
import uuid

from django.conf import settings as django_settings
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.utils.timezone import utc

CHUNKSIZE = 64 * 1024
LOGGER = logging.getLogger('teamplayer.lib')


def list_iter(list_, previous=None):
    if not list_:
        return

    my_list = list_[:]
    if previous is not None:
        index = my_list.index(previous)
        my_list = my_list[index + 1:] + my_list[:index + 1]

    for item in my_list:
        yield item


def get_random_filename(ext=None):
    """
    As the name implies, returns a random filename. if ext is supplied,
    the filename will have an .ext extension
    """
    uuid_str = str(uuid.uuid4()).replace('-', '')[::2]
    if ext is not None and isinstance(ext, basestring):
        uuid_str = '{0}.{1}'.format(uuid_str, ext)
    return uuid_str


def mktemp_file_from_request(request):
    """Helper function to return a temporary file from a request (body)"""
    temp_file = tempfile.TemporaryFile()

    while True:
        data = request.read(CHUNKSIZE)
        if not data:
            break
        temp_file.write(data)

    temp_file.flush()
    temp_file.seek(0)
    return temp_file


def get_user_from_session_id(session_id):
    """Given the session_id, return the user associated with it.

    Raise User.DoesNotExist if session_id does not associate with a user.
    """
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        raise User.DoesNotExist

    try:
        user_id = session.get_decoded().get('_auth_user_id')
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise
    return user


def get_station_id_from_session_id(session_id):
    """Like above, but return the station_id or None."""
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        return None

    return session.get_decoded().get('station_id', None)


def now():
    """Like datetime.datetime.utcnow(), but with tzinfo"""
    return datetime.datetime.utcnow().replace(tzinfo=utc)


def copy_entry_to_queue(entry, mpc):
    """
    Given Entry entry, copy it to the mpc queue directory as efficiently as
    possible.
    """
    song = entry.song
    user = entry.queue.user
    filename = os.path.join(django_settings.MEDIA_ROOT, song.name)
    basename = os.path.basename(filename)

    new_filename = '{0}-{1}'.format(user.pk, basename)
    LOGGER.debug('copying to %s', new_filename)

    new_path = os.path.join(mpc.queue_dir, new_filename)

    # First we try to make a hard link for efficiency
    try:
        if os.path.exists(new_path):
            os.unlink(new_path)
        os.link(filename, new_path)
    except OSError:
        shutil.copy(filename, new_path)

    return new_filename


def first_or_none(d, key):
    """
    Given the dict d, get the item with the given key. If key is not in
    the dict, return None. If it does exist and the value is a list,
    return the first item in the list. If the list is empty return none.
    If the value is not a list, simply return the value.
    """
    if key not in d:
        return None

    value = d[key]
    if isinstance(value, list):
        if len(value) >= 1:
            return value[0]
        else:
            return None
    return value

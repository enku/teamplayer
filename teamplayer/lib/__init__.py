"""TeamPlayer Library package"""
import datetime
import os
import tempfile
import uuid

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import utc

CHUNKSIZE = 64 * 1024


def list_iter(list_, previous=None):
    if not list_:
        return

    my_list = list_[:]
    if previous is not None:
        try:
            index = my_list.index(previous)
            my_list = my_list[index + 1:] + my_list[:index + 1]
        except ValueError:
            pass

    for item in my_list:
        yield item


def get_random_filename(ext=None):
    """
    As the name implies, returns a random filename. if ext is supplied,
    the filename will have an .ext extension
    """
    uuid_str = str(uuid.uuid4()).replace('-', '')[::2]
    if ext is not None and isinstance(ext, str):
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


def get_player_from_session_id(session_id):
    """Given the session_id, return the user associated with it.

    Raise ObjectDoesNotExist if session_id does not associate with a user.
    """
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        raise ObjectDoesNotExist

    try:
        user_id = session.get_decoded().get('_auth_user_id')
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ObjectDoesNotExist
    return user.player


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


def remove_pedantic():
    """
    Set the PEDANTIC attribute on the ID3 class to False.
    """
    from mutagen import id3

    id3.ID3.PEDANTIC = False


def attempt_file_rename(fullpath):
    """Attempt to rename a non-UTF-8 filename

    This only attempts to rename the basename.  If the directory name is not
    valid UTF-8 then no attempt is made.

    If the filename could be renamed, the new name is returned.  Otherwise None
    is returned.

    If the filename was not changed None is returned.

    ``fullpath`` is str, not bytes.
    """
    dirname, filename = os.path.split(fullpath)

    if not filename:
        return None

    try:
        dirname.encode('utf-8')
    except UnicodeEncodeError:
        return None

    original_filename = filename
    filename = filename.encode(errors='surrogateescape')

    re_decoded = False
    for encoding in ['latin-1', 'windows-1252']:
        try:
            filename = filename.decode(encoding)
            re_decoded = True
            break
        except UnicodeDecodeError:
            continue

    if not re_decoded:
        return None

    if filename == original_filename:
        return None

    return os.path.join(dirname, filename)

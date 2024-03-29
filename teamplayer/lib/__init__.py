"""TeamPlayer Library package"""

import datetime
import os
import tempfile
import uuid
from typing import BinaryIO, Iterable, Optional, TypeVar, cast

import django.http
import mutagen.mp3
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.exceptions import ObjectDoesNotExist

from teamplayer import models

_T = TypeVar("_T")
CHUNKSIZE = 64 * 1024
utc = datetime.timezone.utc


def list_iter(items: Iterable[_T], start: Optional[_T] = None) -> Iterable[_T]:
    """Yield each item if items

    If start is given and is a member of items, then the item fillowing that one is
    yielded first, and subsequent items are yielded in round-robin fashion back up to
    start. Otherwise items are yielded in the original order they are provided.
    """
    my_list = list(items)

    if start is not None:
        try:
            index = my_list.index(start)
            my_list = my_list[index + 1 :] + my_list[: index + 1]
        except ValueError:
            pass

    for item in my_list:
        yield item


def get_random_filename(ext: str | None = None) -> str:
    """
    As the name implies, returns a random filename. if ext is supplied,
    the filename will have an .ext extension
    """
    uuid_str = str(uuid.uuid4()).replace("-", "")[::2]
    if ext is not None and isinstance(ext, str):
        uuid_str = f"{uuid_str}.{ext}"
    return uuid_str


def mktemp_file_from_request(request: django.http.HttpRequest) -> BinaryIO:
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


def get_player_from_session_id(session_id: str | int) -> "models.Player":
    """Given the session_id, return the user associated with it.

    Raise ObjectDoesNotExist if session_id does not associate with a user.
    """
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        raise ObjectDoesNotExist

    try:
        user_id = cast(int, session.get_decoded().get("_auth_user_id"))
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ObjectDoesNotExist
    return user.player


def get_station_id_from_session_id(session_id: int | str) -> int | None:
    """Like above, but return the station_id or None."""
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        return None

    station_id = session.get_decoded().get("station_id", "")

    return int(station_id) if station_id else None


def now() -> datetime.datetime:
    """Like datetime.datetime.utcnow(), but with tzinfo"""
    return datetime.datetime.utcnow().replace(tzinfo=utc)


def first_or_none(d: mutagen.mp3.EasyMP3, key: str) -> str | None:
    """
    Given the EasyMP3 object d, get the item with the given key. If key is not in the
    dict, return None. If it does exist and the value is a list, return the first item
    in the list. If the list is empty return none.  If the value is not a list, simply
    return the value.
    """
    if key not in d:
        return None

    value = d[key]
    if isinstance(value, list):
        if len(value) >= 1:
            return str(value[0])
        else:
            return None
    return str(value)


def attempt_file_rename(fullpath: str) -> str | None:
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
        dirname.encode("utf-8")
    except UnicodeEncodeError:
        return None

    original_filename = filename
    filename_bytes = filename.encode(errors="surrogateescape")

    re_decoded = False
    for encoding in ["latin-1", "windows-1252"]:
        try:
            filename = filename_bytes.decode(encoding)
            re_decoded = True
            break
        except UnicodeDecodeError:
            continue

    if not re_decoded:
        return None

    if filename == original_filename:
        return None

    return os.path.join(dirname, filename)

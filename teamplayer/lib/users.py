"""
Library for dealing with users
"""

from django.contrib.auth.models import User

from teamplayer import models


def create_user(username, password):
    """Create a (regular) user account"""
    new_user = User()
    new_user.username = username
    new_user.set_password(password)
    new_user.is_active = True
    new_user.save()

    userprofile = models.UserProfile()
    userprofile.user = new_user
    queue = models.Queue()
    queue.save()
    userprofile.queue = queue
    userprofile.save()

    return new_user

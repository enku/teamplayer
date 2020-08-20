# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def create_initial_data(apps, schema_editor):
    """Create the intial DJ Ango User, Queue & Main Station"""
    User = apps.get_model("auth", "User")
    dj_ango = User.objects.create(
        **{
            "username": "DJ Ango",
            "first_name": "DJ",
            "last_name": "Ango",
            "is_active": True,
            "is_superuser": False,
            "is_staff": False,
            "password": "!",
        }
    )

    Queue = apps.get_model("teamplayer", "Queue")
    queue = Queue.objects.create(active=False)

    Player = apps.get_model("teamplayer", "Player")
    player = Player.objects.create(
        **{"auto_mode": True, "dj_name": "", "queue": queue, "user": dj_ango,}
    )

    Station = apps.get_model("teamplayer", "Station")
    Station.objects.create(
        **{"name": "Main Station", "creator": player,}
    )


class Migration(migrations.Migration):

    dependencies = [
        ("teamplayer", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_initial_data),
    ]

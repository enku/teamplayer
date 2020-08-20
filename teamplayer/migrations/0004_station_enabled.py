# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ("teamplayer", "0003_catchup"),
    ]

    operations = [
        migrations.AddField(
            model_name="station",
            name="enabled",
            field=models.BooleanField(default=True),
        ),
    ]

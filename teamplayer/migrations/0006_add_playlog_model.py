# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-05 18:39
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("teamplayer", "0005_move_libraryitem_to_teamplayer")]

    operations = [
        migrations.CreateModel(
            name="PlayLog",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=254)),
                ("artist", models.CharField(max_length=254)),
                ("time", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="teamplayer.Player",
                    ),
                ),
                (
                    "station",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="teamplayer.Station",
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="playlog", unique_together=set([("station", "time")])
        ),
    ]

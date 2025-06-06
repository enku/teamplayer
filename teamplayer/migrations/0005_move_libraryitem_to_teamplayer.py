# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-03 19:10
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("teamplayer", "0004_station_enabled")]

    operations = [
        migrations.CreateModel(
            name="LibraryItem",
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
                ("filename", models.TextField(unique=True)),
                ("filesize", models.IntegerField()),
                ("mimetype", models.TextField()),
                ("artist", models.TextField()),
                ("title", models.TextField()),
                ("album", models.TextField()),
                ("length", models.IntegerField(null=True)),
                ("genre", models.TextField(blank=True, null=True)),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("station_id", models.IntegerField()),
                (
                    "added_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_songs",
                        to="teamplayer.Player",
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="libraryitem", unique_together=set([("artist", "title", "album")])
        ),
    ]

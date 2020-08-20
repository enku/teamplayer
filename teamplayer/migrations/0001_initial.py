# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Entry",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                        primary_key=True,
                    ),
                ),
                ("place", models.IntegerField(default=0)),
                ("song", models.FileField(upload_to="songs")),
                ("title", models.CharField(default="Unknown", max_length=254)),
                ("artist", models.CharField(verbose_name="Unknown", max_length=254)),
                ("filetype", models.CharField(max_length=4)),
            ],
            options={"ordering": ("-place", "id"),},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Mood",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                        primary_key=True,
                    ),
                ),
                ("artist", models.TextField()),
                ("timestamp", models.DateTimeField(auto_now=True, auto_now_add=True)),
            ],
            options={"ordering": ("-timestamp", "artist"),},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Player",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                        primary_key=True,
                    ),
                ),
                ("dj_name", models.CharField(blank=True, max_length=25)),
                ("auto_mode", models.BooleanField(default=False)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Queue",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                        primary_key=True,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Station",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(unique=True, max_length=128)),
                (
                    "creator",
                    models.ForeignKey(
                        to="teamplayer.Player", on_delete=models.CASCADE, unique=True
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name="player",
            name="queue",
            field=models.OneToOneField(to="teamplayer.Queue", on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="player",
            name="user",
            field=models.OneToOneField(
                to=settings.AUTH_USER_MODEL,
                on_delete=models.CASCADE,
                related_name="player",
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="mood",
            name="station",
            field=models.ForeignKey(to="teamplayer.Station", on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="entry",
            name="queue",
            field=models.ForeignKey(to="teamplayer.Queue", on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="entry",
            name="station",
            field=models.ForeignKey(
                to="teamplayer.Station",
                on_delete=models.CASCADE,
                related_name="entries",
            ),
            preserve_default=True,
        ),
    ]

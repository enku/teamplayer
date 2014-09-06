# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('teamplayer', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='SongFile',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('filename', models.TextField(unique=True)),
                ('filesize', models.IntegerField()),
                ('mimetype', models.TextField()),
                ('artist', models.TextField()),
                ('title', models.TextField()),
                ('album', models.TextField()),
                ('length', models.IntegerField(null=True)),
                ('genre', models.TextField()),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('station_id', models.IntegerField()),
                ('added_by', models.ForeignKey(related_name='library_songs', to='teamplayer.Player')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='songfile',
            unique_together=set([('artist', 'title', 'album')]),
        ),
    ]

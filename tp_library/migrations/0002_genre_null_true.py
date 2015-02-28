# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tp_library', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='songfile',
            name='genre',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
    ]

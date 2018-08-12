# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('teamplayer', '0002_initial_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mood',
            name='timestamp',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='station',
            name='creator',
            field=models.OneToOneField(to='teamplayer.Player', on_delete=models.CASCADE),
        ),
    ]

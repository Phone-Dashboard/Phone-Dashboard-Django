# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-20 18:23
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0008_appversion'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='performance_last_updated',
            field=models.DateTimeField(default=datetime.datetime(2019, 7, 20, 18, 23, 27, 845362, tzinfo=utc)),
            preserve_default=False,
        ),
    ]

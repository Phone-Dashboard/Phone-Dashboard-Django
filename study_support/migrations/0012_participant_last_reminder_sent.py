# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-08-09 22:08
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0011_auto_20190808_2125'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='last_reminder_sent',
            field=models.DateTimeField(default=datetime.datetime(2019, 8, 9, 22, 8, 3, 852290, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
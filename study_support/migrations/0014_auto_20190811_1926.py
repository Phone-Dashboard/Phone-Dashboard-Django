# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-11 23:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0013_participant_timezone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participant',
            name='last_reminder_sent',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-11 22:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0012_participant_last_reminder_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='timezone',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]

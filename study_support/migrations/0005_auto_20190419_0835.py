# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-19 12:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0004_auto_20190327_1142'),
    ]

    operations = [
        migrations.AddField(
            model_name='treatmentphase',
            name='calculation_end_offset',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='treatmentphase',
            name='calculation_start_offset',
            field=models.IntegerField(default=1),
        ),
    ]
# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-03-27 16:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0022_auto_20200327_1253'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participant',
            name='identifier',
            field=models.CharField(db_index=True, max_length=1024, unique=True),
        ),
        migrations.AlterField(
            model_name='treatmentphase',
            name='start_date',
            field=models.DateField(db_index=True),
        ),
    ]

# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-19 11:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0014_auto_20190811_1926'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='last_cost',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='participant',
            name='last_cost_observed',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
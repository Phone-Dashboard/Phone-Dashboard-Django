# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-03-19 12:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('study_support', '0020_auto_20191106_0938'),
    ]

    operations = [
        migrations.AddField(
            model_name='appcode',
            name='generate_date',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import datetime
import json

import arrow
import pytz

from django.core.management.base import BaseCommand

from passive_data_kit.models import DataSourceReference, DataGeneratorDefinition, DataPoint

class Command(BaseCommand):
    help = 'Prints participant app usage in minutes on a given date.'

    def add_arguments(self, parser):
        parser.add_argument('--date',
                            type=str,
                            dest='date',
                            required=True,
                            help='Date of app usage in YYY-MM-DD format')

        parser.add_argument('--source',
                            type=str,
                            dest='source',
                            required=True,
                            help='Identifier of participant in question')

        parser.add_argument('--app',
                            type=str,
                            dest='app',
                            required=True,
                            help='Package name of the app in use. (Example: com.google.android.youtube)')

    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        app = options['app']

        source = DataSourceReference.reference_for_source(options['source'])
        generator = DataGeneratorDefinition.objects.get(generator_identifier='pdk-foreground-application')
        # screen_generator = DataGeneratorDefinition.objects.get(generator_identifier='pdk-screen-state')
        budget_generator = DataGeneratorDefinition.objects.get(generator_identifier='full-app-budgets')

        fetch_date = arrow.get(options['date'] + 'T23:59:59+00:00')

        tz_point = DataPoint.objects.filter(source_reference=source, created__lte=fetch_date.datetime).order_by('-created').first()

        if tz_point is not None:
            properties = tz_point.fetch_properties()

            my_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])
            user_agent = tz_point.fetch_user_agent()

            start_date = my_tz.localize(datetime.datetime(fetch_date.year, fetch_date.month, fetch_date.day, 0, 0, 0, 0))
            end_date = start_date + datetime.timedelta(days=1)

            print('start_date: %s', start_date.isoformat())
            print('end_date: %s', end_date.isoformat())

            on_sum = 0
            off_sum = 0

            dupe_count = 0

            last_usage = None

            budget = DataPoint.objects.filter(source_reference=source, generator_definition=budget_generator, created__lte=start_date).order_by('-created').first()

            budgets = sorted(budget.fetch_properties()['budgets'], key=lambda budget_item: budget_item['effective_on'], reverse=True)

            day_start = arrow.get(start_date).timestamp * 1000

            budget_item = None

            for item in budgets:
                if budget_item is None and day_start >= item['effective_on']:
                    budget_item = item

            limits = json.loads(budget_item['budget'])

            app_limit = -1

            if app in limits:
                app_limit = limits[app]

            while start_date < end_date:
                slice_start = start_date
                slice_end = slice_start + datetime.timedelta(seconds=60)

                for app_use in DataPoint.objects.filter(source_reference=source, generator_definition=generator, secondary_identifier=app, created__gte=slice_start, created__lt=slice_end).order_by('created'):
                    app_properties = app_use.fetch_properties()

    #                last_screen = DataPoint.objects.filter(source_reference=source, generator_definition=screen_generator, created__lt=app_use.created).order_by('-created').first()
    #                state = last_screen.fetch_secondary_identifier()

                    duration = app_properties['duration']

                    if last_usage is None:
                        last_usage = app_use.created
                    else:
                        delta = (app_use.created - last_usage).total_seconds() * 1000

                        if delta < duration:
                            dupe_count += 1

                            duration = delta

                        last_usage = app_use.created

                    if app_properties['screen_active']:
                        on_sum += duration
                    else:
                        off_sum += duration

                if on_sum > 0:
                    print('SUM[%s]: %s / %s -- %s -- %s' % (start_date.isoformat(), on_sum, off_sum, (dupe_count * 5000), app_limit))

                start_date = slice_end

            print('UA: %s' % user_agent)

            if app_limit < 0:
                print('NO LIMIT SET')
            elif on_sum <= app_limit:
                print('OK - DID NOT HIT LIMIT')
            else:
                print('ERROR - EXCEEDED LIMIT')

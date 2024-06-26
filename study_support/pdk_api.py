# pylint: disable=line-too-long, no-member, too-many-lines

import bz2
import codecs
import csv
import datetime
import gc
import json
import io
import os
import sys
import tempfile
import traceback

from zipfile import ZipFile

import arrow
import pytz

from django.conf import settings
from django.core import management
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from passive_data_kit.generators.pdk_foreground_application import fetch_app_genre
from passive_data_kit.models import DataPoint, DataSource, DataGeneratorDefinition, DataSourceReference, DataBundle, install_supports_jsonfield

from study_support.models import Participant


CUSTOM_GENERATORS = (
    'nyu-full-export',
    'nyu-daily-usage-summary',
    'nyu-app-budgets',
    'nyu-snooze-costs',
    'nyu-snooze-events',
    'nyu-snooze-warnings',
    'nyu-participant-status',
    'nyu-violator-usage',
    'nyu-participant-opt-out',
    'nyu-latest-usage-summaries',
    'nyu-participants',
    'nyu-active-users',
    'nyu-snooze-delays',
    'phone-dashboard-yesterday-summaries',
)

# https://docs.python.org/2.7/library/csv.html#examples

class UnicodeWriter:
    def __init__(self, file_output, dialect=csv.excel, encoding="utf-8", **kwds):
        self.queue = io.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = file_output
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        '''writerow(unicode) -> None
        This function takes a Unicode string and encodes it to the output.
        '''

        encoded_row = []

        for value in row:
            encoded_row.append(value)

        self.writer.writerow(encoded_row)
        data = self.queue.getvalue()
        # data = data.decode("utf-8")
        # data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def generators_for_extra_generator(generator):
    generators = []

    if generator in CUSTOM_GENERATORS:
        generators.append('pdk-foreground-application')

    return generators


def compile_report(generator, sources, data_start=None, data_end=None, date_type='created'): # pylint: disable=too-many-locals, too-many-branches, too-many-statements, too-many-return-statements
    try:
        if (generator in CUSTOM_GENERATORS) is False:
            return None

        now = arrow.get()
        filename = tempfile.gettempdir() + '/pdk_export_' + str(now.timestamp()) + str(now.microsecond / 1e6) + '.txt'

        if generator == 'nyu-full-export':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = csv.writer(outfile, delimiter='\t')
                # writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'Source',
                    'Date Created',
                    'Date Recorded',
                    'Time Zone',
                    'Device',
                    'Duration',
                    'Foreground App',
                    'Play Store Category',
                    'Screen Active',
                    'Device Runtime',
                    'App Runtime',
                    'Battery Level',
                    'User Mode',
                ]

                writer.writerow(columns)

                for source in sources: # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        source_reference = DataSourceReference.reference_for_source(source)

                        points = DataPoint.objects.filter(source_reference=source_reference)

                        if data_start is not None:
                            if date_type == 'recorded':
                                points = points.filter(recorded__gte=data_start)
                            else:
                                points = points.filter(created__gte=data_start)

                        if data_end is not None:
                            if date_type == 'recorded':
                                points = points.filter(recorded__lte=data_end)
                            else:
                                points = points.filter(created__lte=data_end)

                        app_points = []

                        apps_def = DataGeneratorDefinition.definition_for_identifier('pdk-foreground-application')

                        point_count = points.filter(generator_definition=apps_def).count()
                        point_index = 0

                        while point_index < point_count:
                            for point in points.filter(generator_definition=apps_def).order_by('created')[point_index:(point_index + 5000)]:
                                properties = point.fetch_properties()

                                app_points.append((point.created, point.recorded, properties,))

                            point_index += 5000

                        status_points = []

                        status_def = DataGeneratorDefinition.definition_for_identifier('pdk-system-status')

                        point_count = points.filter(generator_definition=status_def).count()
                        point_index = 0

                        while point_index < point_count:
                            for point in points.filter(generator_definition=status_def).order_by('created')[point_index:(point_index + 5000)]:
                                properties = point.fetch_properties()

                                status_points.append((point.created, point.recorded, properties,))

                            point_index += 5000

                        battery_points = []

                        battery_def = DataGeneratorDefinition.definition_for_identifier('pdk-device-battery')

                        point_count = points.filter(generator_definition=battery_def).count()
                        point_index = 0

                        while point_index < point_count:
                            for point in points.filter(generator_definition=battery_def).order_by('created')[point_index:(point_index + 5000)]:
                                properties = point.fetch_properties()

                                battery_points.append((point.created, point.recorded, properties,))

                            point_index += 5000

                        user_points = []

                        user_def = DataGeneratorDefinition.definition_for_identifier('pdk-user')

                        point_count = points.filter(generator_definition=user_def).count()
                        point_index = 0

                        while point_index < point_count:
                            for point in points.filter(generator_definition=user_def).order_by('created'):
                                properties = point.fetch_properties()

                                user_points.append((point.created, point.recorded, properties,))

                            point_index += 5000

                        last_seen = None

                        for point in app_points:
                            if last_seen != point[0]:
                                here_tz = pytz.timezone(point[2]['passive-data-metadata']['timezone'])

                                row = []

                                row.append(source)

                                created = point[0].astimezone(here_tz)

                                row.append(created.isoformat())

                                recorded = point[1].astimezone(here_tz)

                                row.append(recorded.isoformat())

                                row.append(point[2]['passive-data-metadata']['timezone'])

                                model = point[2]['passive-data-metadata']['generator'].split(';')[-1].strip().replace(')', '')

                                row.append(model)

                                if last_seen is None:
                                    row.append(point[2]['duration'])
                                elif (point[0] - last_seen).total_seconds() * 1000 < point[2]['duration']:
                                    row.append((point[0] - last_seen).total_seconds() * 1000)
                                else:
                                    row.append(point[2]['duration'])

                                if 'application' in point[2]:
                                    row.append(point[2]['application'])
                                    row.append(fetch_app_genre(point[2]['application']))
                                else:
                                    row.append('')
                                    row.append('')

                                if point[2]['screen_active']:
                                    row.append(1)
                                else:
                                    row.append(0)

                                last_status = None

                                for status in status_points:
                                    if status[0] < point[0]:
                                        last_status = status
                                    else:
                                        break

                                if last_status is not None:
                                    if 'system_runtime' in last_status[2]:
                                        row.append(last_status[2]['system_runtime'])
                                    else:
                                        row.append(None)

                                    row.append(last_status[2]['runtime'])
                                else:
                                    row.append(None)
                                    row.append(None)

                                last_battery = None

                                for status in battery_points:
                                    if status[0] < point[0]:
                                        last_battery = status
                                    else:
                                        break

                                if last_battery is not None:
                                    row.append(100.0 * (float(last_battery[2]['level']) / float(last_battery[2]['scale'])))
                                else:
                                    row.append(None)

                                last_user = None

                                for status in user_points:
                                    if status[0] < point[0]:
                                        last_user = status
                                    else:
                                        break

                                if last_user is not None and ('mode' in last_user[2]):
                                    row.append(last_user[2]['mode'])
                                else:
                                    row.append(None)

                                writer.writerow(row)

                                last_seen = point[0]

            return filename

        if generator == 'nyu-daily-usage-summary':
            start_date = timezone.now().date() - datetime.timedelta(days=30)

            if data_start is not None:
                start_date = data_start.date()

            if data_end is None:
                data_end = timezone.now()

            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'Source',
                    'Date',
                    'Usage (Milliseconds)',
                ]

                writer.writerow(columns)

                for source in sources:
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            participant = Participant.objects.filter(identifier=source).first()

                            if participant is not None:
                                index_date = start_date

                                while index_date <= data_end.date():
                                    usage = participant.fetch_usage_for_date(index_date)

                                    row = [source, index_date.isoformat(), usage]

                                    writer.writerow(row)

                                    index_date = index_date + datetime.timedelta(days=1)
                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-app-budgets-daily':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'App Code',
                    'Updated',
                    'App',
                    'Play Store Category',
                    'Effective Date',
                    'New Limit',
                    'Time Zone',
                ]

                writer.writerow(columns)

                for source in sources: # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            source_reference = DataSourceReference.reference_for_source(source)
                            budget_def = DataGeneratorDefinition.definition_for_identifier('daily-app-budget')

                            points = DataPoint.objects.filter(source_reference=source_reference, generator_definition=budget_def)

                            if data_start is not None:
                                points = points.filter(created__gte=data_start)

                            if data_end is not None:
                                points = points.filter(created__lt=data_end)

                            old_budget_packages = None

                            for point in points.order_by('created'):
                                properties = point.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                budget = json.loads(properties['budget'])

                                new_budget_packages = []

                                for key, value in budget.iteritems():
                                    row = []

                                    row.append(source)
                                    row.append(point.created.astimezone(here_tz).isoformat())
                                    row.append(key)
                                    row.append(fetch_app_genre(key))
                                    row.append(datetime.datetime.fromtimestamp(properties['effective_on'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())
                                    row.append(value)
                                    row.append(properties['passive-data-metadata']['timezone'])

                                    writer.writerow(row)

                                    if (key in new_budget_packages) is False:
                                        new_budget_packages.append(key)

                                if old_budget_packages is not None:
                                    for package in new_budget_packages:
                                        if package in old_budget_packages: # pylint: disable=unsupported-membership-test
                                            old_budget_packages.remove(package)

                                    for package in old_budget_packages: # pylint: disable=not-an-iterable
                                        row = []

                                        row.append(source)
                                        row.append(point.created.astimezone(here_tz).isoformat())
                                        row.append(package)
                                        row.append(fetch_app_genre(package))
                                        row.append(datetime.datetime.fromtimestamp(properties['effective_on'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())
                                        row.append(-1)
                                        row.append(properties['passive-data-metadata']['timezone'])

                                        writer.writerow(row)

                                old_budget_packages = new_budget_packages

                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-app-budgets':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'App Code',
                    'Updated',
                    'App',
                    'Play Store Category',
                    'Effective Date',
                    'New Limit',
                    'Time Zone',
                ]

                writer.writerow(columns)

                budget_def = DataGeneratorDefinition.definition_for_identifier('full-app-budgets')

                for source in sources: # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        source_reference = DataSourceReference.reference_for_source(source)

                        try:
                            latest = DataPoint.objects.filter(source_reference=source_reference, generator_definition=budget_def).order_by('-created').first()

                            old_budget_packages = None

                            if latest is not None:
                                properties = latest.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                budgets = properties['budgets']

                                for item in budgets:
                                    budget = json.loads(item['budget'])

                                    new_budget_packages = []

                                    for key, value in budget.iteritems():
                                        row = []

                                        row.append(source)
                                        row.append(datetime.datetime.fromtimestamp(item['observed'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())
                                        row.append(key)
                                        row.append(fetch_app_genre(key))
                                        row.append(datetime.datetime.fromtimestamp(item['effective_on'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())
                                        row.append(value)
                                        row.append(properties['passive-data-metadata']['timezone'])

                                        writer.writerow(row)

                                        if (key in new_budget_packages) is False:
                                            new_budget_packages.append(key)

                                    if old_budget_packages is not None:
                                        for package in new_budget_packages:
                                            if package in old_budget_packages: # pylint: disable=unsupported-membership-test
                                                old_budget_packages.remove(package)

                                        for package in old_budget_packages: # pylint: disable=not-an-iterable
                                            row = []

                                            row.append(source)
                                            row.append(datetime.datetime.fromtimestamp(item['observed'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())
                                            row.append(package)
                                            row.append(fetch_app_genre(package))
                                            row.append(datetime.datetime.fromtimestamp(item['effective_on'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())
                                            row.append(-1)
                                            row.append(properties['passive-data-metadata']['timezone'])

                                            writer.writerow(row)

                                    old_budget_packages = new_budget_packages

                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-snooze-costs':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'App Code',
                    'Updated',
                    'Recorded',
                    'Price Per Snooze',
                ]

                writer.writerow(columns)

                for source in sources:
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            source_reference = DataSourceReference.reference_for_source(source)
                            event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                            points = DataPoint.objects.filter(source_reference=source_reference, generator_definition=event_def, secondary_identifier='set-snooze-cost')

                            points = DataPoint.objects.filter(source=source, generator_identifier='pdk-app-event', secondary_identifier='set-snooze-cost')

                            if data_start is not None:
                                if date_type == 'recorded':
                                    points = points.filter(recorded__gte=data_start)
                                else:
                                    points = points.filter(created__gte=data_start)

                            if data_end is not None:
                                if date_type == 'recorded':
                                    points = points.filter(recorded__lt=data_end)
                                else:
                                    points = points.filter(created__lt=data_end)

                            for point in points:
                                properties = point.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                row = []

                                row.append(source)
                                row.append(point.created.astimezone(here_tz).isoformat())
                                row.append(point.recorded.astimezone(here_tz).isoformat())
                                row.append(round(properties['event_details']['snooze-cost'], 2))

                                writer.writerow(row)
                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-snooze-events':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'App Code',
                    'Created',
                    'Recorded',
                    'App',
                    'Play Store Category',
                    'Price Per Snooze',
                    'Initial Budget',
                    'Remaining Budget',
                    'Limit Extension'
                ]

                writer.writerow(columns)

                event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')
                snooze_def = DataGeneratorDefinition.definition_for_identifier('app-snooze')

                for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            source_ref = DataSourceReference.reference_for_source(source)

                            costs = []

                            points = DataPoint.objects.filter(source_reference=source_ref, generator_definition=event_def, secondary_identifier='set-snooze-cost').order_by('created')

                            for point in points:
                                properties = point.fetch_properties()

                                costs.append((point.created, properties['event_details']['snooze-cost']))

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                            points = DataPoint.objects.filter(source_reference=source_ref, generator_definition=snooze_def)

                            if data_start is not None:
                                if date_type == 'recorded':
                                    points = points.filter(recorded__gte=data_start)
                                else:
                                    points = points.filter(created__gte=data_start)

                            if data_end is not None:
                                if date_type == 'recorded':
                                    points = points.filter(recorded__lt=data_end)
                                else:
                                    points = points.filter(created__lt=data_end)

                            points = points.order_by('created')

                            for point in points:
                                properties = point.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                row = []

                                row.append(source)
                                row.append(point.created.astimezone(here_tz).isoformat())
                                row.append(point.recorded.astimezone(here_tz).isoformat())
                                row.append(properties['app_package'])
                                row.append(fetch_app_genre(properties['app_package']))

                                snooze_cost = None

                                for cost in costs:
                                    if cost[0] < point.created:
                                        snooze_cost = cost

                                if snooze_cost is not None:
                                    row.append(round(snooze_cost[1], 2))
                                else:
                                    row.append('')

                                if 'initial_budget' in properties:
                                    row.append(properties['initial_budget'])
                                else:
                                    row.append('')

                                if 'remaining_budget' in properties:
                                    row.append(properties['remaining_budget'])
                                else:
                                    row.append('')

                                if 'duration' in properties:
                                    row.append(properties['duration'])
                                else:
                                    row.append('')

                                writer.writerow(row)

                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-snooze-warnings':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'App Code',
                    'Created',
                    'Hour of Day',
                    'Recorded',
                    'App',
                    'App Category',
                    'Event',
                    'Minutes',
                    'Delay',
                    'Snooze Extension',
                ]

                writer.writerow(columns)

                event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                secondary_identifiers = [
                    'blocked_app',
                    'app-block-warning',
                    'closed-warning',
                    'app-blocked-can-snooze',
                    'skipped-snooze',
                    'cancelled-snooze',
                    'snoozed-app-limit',
                    'app-blocked-no-snooze',
                    'app-blocked-no-snooze-closed',
                    'app-blocked-delayed',
                    'closed-delay-warning',
                ]

                secondary = None

                for identifier in secondary_identifiers:
                    if secondary is None:
                        secondary = Q(secondary_identifier=identifier)
                    else:
                        secondary = secondary | Q(secondary_identifier=identifier) # pylint: disable=unsupported-binary-operation

                query = Q(generator_definition=event_def) & secondary

                if data_start is not None:
                    if date_type == 'recorded':
                        query = query & Q(recorded__gte=data_start)
                    else:
                        query = query & Q(created__gte=data_start)

                if data_end is not None:
                    if date_type == 'recorded':
                        query = query & Q(recorded__gte=data_end)
                    else:
                        query = query & Q(created__lt=data_end)

                for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            source_ref = DataSourceReference.reference_for_source(source)

                            points = DataPoint.objects.filter(source_reference=source_ref).filter(query).order_by('created')

                            for point in points:
                                properties = point.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                row = []

                                row.append(source)

                                created = point.created.astimezone(here_tz)

                                row.append(created.isoformat())
                                row.append(created.hour)
                                row.append(point.recorded.astimezone(here_tz).isoformat())

                                if 'package' in properties['event_details']:
                                    row.append(properties['event_details']['package'])
                                    row.append(fetch_app_genre(properties['event_details']['package']))
                                else:
                                    row.append('')
                                    row.append('')

                                if properties['event_name'] == 'app-blocked-delayed':
                                    row.append('App Blocked Until Delay Elapsed')

                                    if 'snooze-minutes' in properties['event_details']:
                                        row.append(properties['event_details']['snooze-minutes'])
                                    else:
                                        row.append('')

                                    if 'snooze-delay' in properties['event_details']:
                                        row.append(properties['event_details']['snooze-delay'])
                                    else:
                                        row.append('')
                                elif properties['event_name'] == 'app-blocked-can-snooze':
                                    row.append('App Blocked - Snooze Offered')
                                elif properties['event_name'] == 'app-blocked-no-snooze':
                                    row.append('App Blocked - Snooze Unavailable')
                                elif properties['event_name'] == 'app-block-warning':
                                    row.append('App Warning Displayed')
                                    row.append(properties['event_details']['minutes-remaining'])
                                elif properties['event_name'] == 'skipped-snooze':
                                    row.append('User Declined Snooze')
                                elif properties['event_name'] == 'closed-warning':
                                    row.append('User Closed Warning')
                                    row.append(properties['event_details']['minutes-remaining'])
                                elif properties['event_name'] == 'snoozed-app-limit':
                                    row.append('Snooze Enabled')

                                    row.append('')

                                    if 'snooze-delay' in properties['event_details']:
                                        row.append(properties['event_details']['snooze-delay'])
                                    else:
                                        row.append('')

                                    if 'snooze-minutes' in properties['event_details']:
                                        row.append(properties['event_details']['snooze-minutes'] * (60 * 1000))
                                    else:
                                        row.append('')

                                elif properties['event_name'] == 'cancelled-snooze':
                                    row.append('User Cancelled Snooze')
                                elif properties['event_name'] == 'closed-delay-warning':
                                    row.append('User Closed Delay Warning')

                                    if 'snooze-minutes' in properties['event_details']:
                                        row.append(properties['event_details']['snooze-minutes'])
                                    else:
                                        row.append('')

                                    if 'snooze-delay' in properties['event_details']:
                                        row.append(properties['event_details']['snooze-delay'])
                                    else:
                                        row.append('')

                                elif properties['event_name'] == 'app-blocked-no-snooze-closed':
                                    row.append('User Closed App Blocked (No Snooze) Warning')
                                elif properties['event_name'] == 'blocked_app':
                                    row.append('System started app block process')
                                else:
                                    row.append('')

                                writer.writerow(row)

                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-participant-status':
            with open(filename, 'w', encoding='utf-8') as outfile:
                event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'Participant',
                    'Group',
                    'Blocker',
                    'Usage Change',
                    'Snooze Cost',
                    'App Limits',
                    'Snoozes',
                    'Last Upload',
                    'Last Upload Delay',
                    'App Version',
                    'Platform Version',
                    'Phone Model',
                    'Opted Out',
                    'E-Mail Enabled',
                    'PhaseUseOverall (ms)',
                    'PhaseUseFB (ms)',
                    'PhaseUseIG (ms)',
                    'PhaseUseSnap (ms)',
                    'PhaseUseYoutube (ms)',
                    'PhaseUseBrowser (ms)',
                    'Misc. Issues',
                    'All Permission Issues',
                    'Window Permission',
                    'App Usage Permission',
                ]

                writer.writerow(columns)

                for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            participant = Participant.objects.filter(identifier=source).first()

                            if participant is not None:
                                try:
                                    report = json.loads(participant.metadata)['study_performance_report']

                                    row = []
                                    row.append(participant.identifier)

                                    row.append(report['group'])

                                    row.append(report['phase_type'])
                                    row.append(report['today_observed_fraction'])

                                    if report['phase_snooze_cost_overdue']:
                                        row.append('Overdue')
                                    else:
                                        row.append('OK')

                                    if report['phase_budget'] is not None:
                                        row.append(len(report['phase_budget']))
                                    else:
                                        row.append('')

                                    row.append(report['phase_snoozes'])
                                    row.append(report['latest_point'])
                                    row.append(report['latest_ago'])

                                    if 'app_version' in report:
                                        row.append(report['app_version'])
                                    else:
                                        row.append('')

                                    if 'platform_version' in report:
                                        row.append(report['platform_version'])
                                    else:
                                        row.append('')

                                    if 'device_model' in report:
                                        row.append(report['device_model'])
                                    else:
                                        row.append('')

                                    source_reference = DataSourceReference.reference_for_source(source)

                                    points = DataPoint.objects.filter(source_reference=source_reference, generator_definition=event_def, secondary_identifier='app-opt-out')

                                    if points.first() is not None:
                                        row.append(1)
                                    else:
                                        row.append(0)

                                    if participant.email_enabled:
                                        row.append(1)
                                    else:
                                        row.append(0)

                                    points = DataPoint.objects.filter(source_reference=source_reference, generator_definition=event_def, secondary_identifier='app-usage-summary')

                                    if data_start is not None:
                                        if date_type == 'recorded':
                                            points = points.filter(recorded__gte=data_start)
                                        else:
                                            points = points.filter(created__gte=data_start)

                                    if data_end is not None:
                                        if date_type == 'recorded':
                                            points = points.filter(recorded__lte=data_end)
                                        else:
                                            points = points.filter(created__lte=data_end)

                                    point = points.order_by('-created').first()

                                    if point is not None:
                                        properties = point.fetch_properties()

                                        if 'phase' in properties['event_details']:
                                            phase = properties['event_details']['phase']

                                            usage_sum = 0

                                            apps = ['facebook', 'instagram', 'snapchat', 'youtube', 'browser']

                                            for package in phase:
                                                if (package in apps) is False:
                                                    usage = phase[package]

                                                    if 'usage_ms' in usage:
                                                        try:
                                                            usage_sum += int(usage['usage_ms'])
                                                        except ValueError:
                                                            pass

                                            row.append(usage_sum)

                                            for app in apps:
                                                if app in phase:
                                                    usage = phase[app]

                                                    if 'usage_ms' in usage:
                                                        try:
                                                            row.append(int(usage['usage_ms']))
                                                        except ValueError:
                                                            row.append('')
                                                    else:
                                                        row.append('')
                                                else:
                                                    row.append('')
                                        else:
                                            row.append('')
                                            row.append('')
                                            row.append('')
                                            row.append('')
                                            row.append('')
                                            row.append('')
                                    else:
                                        row.append('')
                                        row.append('')
                                        row.append('')
                                        row.append('')
                                        row.append('')
                                        row.append('')

                                    issues = ''

                                    for issue in report['phase_misc_issues']:
                                        if issues != '':
                                            issues += '; '

                                        issues += issue

                                    row.append(issues)

                                    points = DataPoint.objects.filter(source_reference=source_reference, generator_definition=event_def, secondary_identifier='nyu-app-issue-notification')

                                    if data_start is not None:
                                        if date_type == 'recorded':
                                            points = points.filter(recorded__gte=data_start)
                                        else:
                                            points = points.filter(created__gte=data_start)

                                    if data_end is not None:
                                        if date_type == 'recorded':
                                            points = points.filter(recorded__lte=data_end)
                                        else:
                                            points = points.filter(created__lte=data_end)

                                    missing_permissions = set()

                                    for point in points:
                                        properties = point.fetch_properties()

                                        if 'issues' in properties['event_details']:
                                            issues_str = properties['event_details']['issues']

                                            for issue in issues_str.split(';'):
                                                if issue:
                                                    missing_permissions.add(issue)

                                    missing_permissions_str = ''

                                    if len(missing_permissions) > 0: # pylint: disable=len-as-condition
                                        missing_permissions_str = ';'.join(missing_permissions)

                                    row.append(missing_permissions_str)

                                    if 'missing-window-permissions' in missing_permissions:
                                        row.append('Missing')
                                    else:
                                        row.append('OK')

                                    if 'missing-app-usage' in missing_permissions:
                                        row.append('Missing')
                                    else:
                                        row.append('OK')

                                    writer.writerow(row)
                                except KeyError:
                                    print('No performance report compiled for ' + str(source) + '.')

                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-violator-usage':
            server_tz = pytz.timezone(settings.TIME_ZONE)

            end = timezone.now().astimezone(server_tz)

            end = end - datetime.timedelta(seconds=((end.minute * 60) + end.second), microseconds=end.microsecond)

            start = end - datetime.timedelta(minutes=(12 * 60)) # pylint: disable=superfluous-parens

            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'Participant',
                    'Facebook Usage',
                    'Instagram Usage',
                    'Snapchat Usage',
                    'First Use',
                    'Last Use',
                    'Monitor Start',
                    'Monitor End',
                    'Facebook Start',
                    'Facebook End',
                    'Instagram Start',
                    'Instagram End',
                    'Snapchat Start',
                    'Snapchat End',
                ]

                writer.writerow(columns)

                app_def = DataGeneratorDefinition.definition_for_identifier('pdk-foreground-application')

                for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                    data_source = DataSource.objects.filter(identifier=source).first()

                    if data_source is not None and data_source.server is None:
                        try:
                            participant = Participant.objects.filter(identifier=source).first()

                            if participant is not None:
                                source_ref = DataSourceReference.reference_for_source(source)

                                points = DataPoint.objects.filter(source_reference=source_ref, generator_definition=app_def)

                                points = points.filter(recorded__gte=start, recorded__lt=end)

                                earliest = None
                                latest = None

                                facebook_apps = [
                                    'com.facebook.katana',
                                    'com.facebook.lite',
                                ]

                                facebook_usage = 0.0

                                facebook_start = None
                                facebook_end = None

                                for app in facebook_apps:
                                    last_seen = None

                                    for point in points.filter(secondary_identifier=app):
                                        properties = point.fetch_properties()

                                        if properties['screen_active']:
                                            if last_seen is None:
                                                facebook_usage += properties['duration']
                                            elif (point.created - last_seen).total_seconds() * 1000 < properties['duration']:
                                                facebook_usage += (point.created - last_seen).total_seconds() * 1000
                                            else:
                                                facebook_usage += properties['duration']

                                            last_seen = point.created

                                            created = point.created.astimezone(server_tz)

                                            if earliest is None:
                                                earliest = created
                                            elif created < earliest:
                                                earliest = created

                                            if latest is None:
                                                latest = created
                                            elif point.created > latest:
                                                latest = created

                                            if facebook_start is None:
                                                facebook_start = created
                                            elif point.created < facebook_start:
                                                facebook_start = created

                                            if facebook_end is None:
                                                facebook_end = created
                                            elif point.created > facebook_end:
                                                facebook_end = created

                                instagram_apps = [
                                    'com.instagram.android',
                                ]

                                instagram_usage = 0.0

                                instagram_start = None
                                instagram_end = None

                                for app in instagram_apps:
                                    last_seen = None

                                    for point in points.filter(secondary_identifier=app):
                                        properties = point.fetch_properties()

                                        if properties['screen_active']:
                                            if last_seen is None:
                                                instagram_usage += properties['duration']
                                            elif (point.created - last_seen).total_seconds() * 1000 < properties['duration']:
                                                instagram_usage += (point.created - last_seen).total_seconds() * 1000
                                            else:
                                                instagram_usage += properties['duration']

                                            last_seen = point.created

                                            created = point.created.astimezone(server_tz)

                                            if earliest is None:
                                                earliest = created
                                            elif created < earliest:
                                                earliest = created

                                            if latest is None:
                                                latest = created
                                            elif point.created > latest:
                                                latest = created

                                            if instagram_start is None:
                                                instagram_start = created
                                            elif point.created < instagram_start:
                                                instagram_start = created

                                            if instagram_end is None:
                                                instagram_end = created
                                            elif point.created > instagram_end:
                                                instagram_end = created

                                snapchat_apps = [
                                    'com.snapchat.android',
                                ]

                                snapchat_usage = 0.0

                                snapchat_start = None
                                snapchat_end = None

                                for app in snapchat_apps:
                                    last_seen = None

                                    for point in points.filter(secondary_identifier=app):
                                        properties = point.fetch_properties()

                                        if properties['screen_active']:
                                            if last_seen is None:
                                                snapchat_usage += properties['duration']
                                            elif (point.created - last_seen).total_seconds() * 1000 < properties['duration']:
                                                snapchat_usage += (point.created - last_seen).total_seconds() * 1000
                                            else:
                                                snapchat_usage += properties['duration']

                                            created = point.created.astimezone(server_tz)

                                            if earliest is None:
                                                earliest = created
                                            elif created < earliest:
                                                earliest = created

                                            if latest is None:
                                                latest = created
                                            elif point.created > latest:
                                                latest = created

                                            if snapchat_start is None:
                                                snapchat_start = created
                                            elif point.created < snapchat_start:
                                                snapchat_start = created

                                            if snapchat_end is None:
                                                snapchat_end = created
                                            elif point.created > snapchat_end:
                                                snapchat_end = created

                                if earliest is not None and latest is not None:
                                    row = []

                                    row.append(participant.identifier)
                                    row.append(facebook_usage / 60000)
                                    row.append(instagram_usage / 60000)
                                    row.append(snapchat_usage / 60000)
                                    row.append(earliest.isoformat())
                                    row.append(latest.isoformat())
                                    row.append(start.isoformat())
                                    row.append(end.isoformat())

                                    if (facebook_start is not None) and (facebook_end is not None):
                                        row.append(facebook_start.isoformat())
                                        row.append(facebook_end.isoformat())
                                    else:
                                        row.append('')
                                        row.append('')

                                    if (instagram_start is not None) and (instagram_end is not None):
                                        row.append(instagram_start.isoformat())
                                        row.append(instagram_end.isoformat())
                                    else:
                                        row.append('')
                                        row.append('')

                                    if (snapchat_start is not None) and (snapchat_end is not None):
                                        row.append(snapchat_start.isoformat())
                                        row.append(snapchat_end.isoformat())
                                    else:
                                        row.append('')
                                        row.append('')

                                    writer.writerow(row)
                        except: # pylint: disable=bare-except
                            traceback.print_exc()

            return filename

        if generator == 'nyu-participant-opt-out':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = UnicodeWriter(outfile, delimiter='\t')

                columns = [
                    'Participant',
                    'Opt-Out Date',
                    'Time Zone',
                ]

                writer.writerow(columns)

                event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                points = DataPoint.objects.filter(generator_definition=event_def, secondary_identifier='app-opt-out').order_by('created')

                for point in points:
                    properties = point.fetch_properties()

                    here_tz = settings.TIME_ZONE

                    if 'timezone' in properties['passive-data-metadata']:
                        here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                    row = []

                    row.append(point.source)

                    created = point.created.astimezone(here_tz)

                    row.append(created.isoformat())

                    row.append(here_tz)

                    writer.writerow(row)

            return filename

        if generator == 'nyu-latest-usage-summaries':
            try:
                filename = filename.replace('.txt', '.zip')

                files_written = 0

                with ZipFile(filename, 'w', allowZip64=True) as export_file:
                    for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                        data_source = DataSource.objects.filter(identifier=source).first()

                        if data_source is not None and data_source.server is None:
                            gc.collect()

                            source_ref = DataSourceReference.reference_for_source(source)
                            event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                            points = DataPoint.objects.filter(source_reference=source_ref, generator_definition=event_def, secondary_identifier='app-usage-summary')

                            if data_end is not None and data_start is not None:
                                if (data_end - data_start).days > 1:
                                    data_start = data_end - datetime.timedelta(days=1)

                            if date_type == 'created':
                                if data_start is not None:
                                    points = points.filter(created__gte=data_start)

                                if data_end is not None:
                                    points = points.filter(created__lte=data_end)

                            if date_type == 'recorded':
                                if data_start is not None:
                                    points = points.filter(recorded__gte=data_start)

                                if data_end is not None:
                                    points = points.filter(recorded__lte=data_end)

                            seen_dates = []

                            latest_point = points.order_by('-created').first()

                            if latest_point is not None:
                                properties = latest_point.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                latest_created = latest_point.created.astimezone(here_tz)

                                earliest_created = points.order_by('created').first().created

                                if data_start is not None and earliest_created < data_start:
                                    earliest_created = latest_created - datetime.timedelta(days=7)

                                index_date = arrow.get(latest_created).replace(hour=0, minute=0, microsecond=0).shift(days=1).datetime

                                while index_date > earliest_created:
                                    point = DataPoint.objects.filter(source_reference=source_ref, generator_definition=event_def, secondary_identifier='app-usage-summary', created__lte=index_date).order_by('-created').first()

                                    if point is not None:
                                        properties = point.fetch_properties()

                                        here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                        created = point.created.astimezone(here_tz)

                                        created_date = created.date()

                                        if (created_date.isoformat() in seen_dates) is False:
                                            export_file.writestr(source + '-alternative-' + created_date.isoformat() + '.json', json.dumps(properties, indent=2))

                                            seen_dates.append(created_date.isoformat())

                                            files_written += 1

                                        if created_date <= earliest_created.date():
                                            break

                                    index_date = arrow.get(index_date).shift(days=-1).datetime

                if files_written > 0:
                    return filename
            except: # pylint: disable=bare-except
                traceback.print_exc()

        if generator == 'nyu-active-users':
            try:
                with open(filename, 'w', encoding='utf-8') as outfile:
                    writer = csv.writer(outfile, delimiter='\t')

                    when = arrow.now().replace(hour=0, minute=0, microsecond=0).shift(days=-1).datetime

                    columns = [
                        'Identifier',
                        'Transmitting',
                        'Active',
                        'Last Data Date',
                    ]

                    writer.writerow(columns)

                    for participant in Participant.objects.all().order_by('identifier'):
                        row = []

                        row.append(participant.identifier)

                        transmitted = 0
                        active = 0
                        last_data_date = None

                        source_ref = DataSourceReference.reference_for_source(participant.identifier)
                        app_def = DataGeneratorDefinition.definition_for_identifier('pdk-foreground-application')

                        for point in DataPoint.objects.filter(source_reference=source_ref, generator_definition=app_def, created__gte=when).order_by('-created'):
                            if transmitted == 0:
                                transmitted = 1

                            if last_data_date is None:
                                last_data_date = point.created

                            properties = point.fetch_properties()

                            if properties['screen_active']:
                                active = 1

                                break

                        row.append(transmitted)
                        row.append(active)

                        if last_data_date is not None:
                            row.append(last_data_date.isoformat())
                        else:
                            row.append('')

                        writer.writerow(row)

                return filename
            except: # pylint: disable=bare-except
                traceback.print_exc()

        if generator == 'nyu-participants':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = csv.writer(outfile, delimiter='\t')

                columns = [
                    'E-Mail',
                    'App Code / Identifier',
                    'Created',
                    'Server',
                ]

                writer.writerow(columns)

                for participant in Participant.objects.all().order_by('-created'):
                    row = []

                    row.append(participant.email_address)
                    row.append(participant.identifier)
                    row.append(participant.created.isoformat())

                    source = DataSource.objects.filter(identifier=participant.identifier).first()

                    if source is not None:
                        row.append(str(source.server))

                    writer.writerow(row)

            return filename

        if generator == 'nyu-snooze-delays':
            with open(filename, 'w', encoding='utf-8') as outfile:
                writer = csv.writer(outfile, delimiter='\t')

                columns = [
                    'App Code',
                    'Snooze Delay',
                    'Updated Datetime',
                    'Effective Datetime',
                ]

                writer.writerow(columns)

                delay_definition = DataGeneratorDefinition.definition_for_identifier('snooze-delay')

                for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                    source_reference = DataSourceReference.reference_for_source(source)

                    for point in DataPoint.objects.filter(generator_definition=delay_definition, source_reference=source_reference).order_by('created'):
                        properties = point.fetch_properties()

                        row = []

                        row.append(point.source)
                        row.append(properties['snooze_delay'])

                        here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                        row.append(point.created.astimezone(here_tz).isoformat())
                        row.append(datetime.datetime.fromtimestamp(properties['effective_on'] / 1000, tz=pytz.utc).astimezone(here_tz).isoformat())

                        writer.writerow(row)

            return filename

        if generator == 'phone-dashboard-yesterday-summaries':
            try:
                with open(filename, 'w', encoding='utf-8') as outfile:
                    writer = csv.writer(outfile, delimiter='\t')

                    columns = [
                        'Participant',
                        'Date',
                        'Package',
                        'Label',
                        'Usage',
                    ]

                    writer.writerow(columns)

                    for source in sorted(sources): # pylint: disable=too-many-nested-blocks
                        print('SOURCE: %s' % source)

                        data_source = DataSource.objects.filter(identifier=source).first()

                        if data_source is not None and data_source.server is None:
                            gc.collect()

                            source_ref = DataSourceReference.reference_for_source(source)
                            event_def = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                            points = DataPoint.objects.filter(source_reference=source_ref, generator_definition=event_def, secondary_identifier='app-usage-summary')

                            if data_end is not None and data_start is not None:
                                if (data_end - data_start).days > 1:
                                    data_start = data_end - datetime.timedelta(days=1)

                            if date_type == 'created':
                                if data_start is not None:
                                    points = points.filter(created__gte=data_start)

                                if data_end is not None:
                                    points = points.filter(created__lte=data_end)

                            if date_type == 'recorded':
                                if data_start is not None:
                                    points = points.filter(recorded__gte=data_start)

                                if data_end is not None:
                                    points = points.filter(recorded__lte=data_end)

                            seen_dates = []

                            latest_point = points.order_by('-created').first()

                            print('latest_point: %s' % latest_point)

                            if latest_point is not None:
                                properties = latest_point.fetch_properties()

                                here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                latest_created = latest_point.created.astimezone(here_tz)

                                earliest_created = points.order_by('created').first().created

                                if data_start is not None and earliest_created < data_start:
                                    earliest_created = data_start

                                index_date = arrow.get(latest_created).replace(hour=0, minute=0, microsecond=0).shift(days=1).datetime

                                while index_date > earliest_created:
                                    print(' %s >? %s' % (index_date, earliest_created))

                                    point = DataPoint.objects.filter(source_reference=source_ref, generator_definition=event_def, secondary_identifier='app-usage-summary', created__lte=index_date).order_by('-created').first()

                                    if point is not None:
                                        properties = point.fetch_properties()

                                        yesterday_summary = properties.get('event_details', {}).get('yesterday-summary', {}).get('apps-usage', {})

                                        if len(yesterday_summary) > 0:
                                            here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                                            created = point.created.astimezone(here_tz)

                                            created_date = created.date()

                                            if (created_date.isoformat() in seen_dates) is False:
                                                seen_dates.append(created_date.isoformat())

                                                for package, usage_data in yesterday_summary.items():
                                                    print('  %s - %s' % (package, usage_data))

                                                    columns = [
                                                        source,
                                                        (created.date() - datetime.timedelta(days=1)).isoformat(),
                                                        package,
                                                        usage_data.get('label', 'Unknown'),
                                                        usage_data.get('usage_ms', 0),
                                                    ]

                                                    writer.writerow(columns)

                                    index_date = arrow.get(index_date).shift(days=-1).datetime

                return filename
            except: # pylint: ignore=bare-except
                traceback.print_exc()
    except: # pylint: disable=bare-except
        print(generator + ': ' + str(sources))

        traceback.print_exc()

    return None

def pdk_custom_home_header():
    participants = []

    for participant in Participant.objects.all():
        try:
            report = json.loads(participant.metadata)['study_performance_report']

            row = {
                'identifier': participant.identifier,
                'performance': report
            }

            participants.append(row)
        except KeyError:
            print('No performance metadata for: ' + participant.identifier)

    context = {}
    context['participants'] = participants

    return render_to_string('phone_dashboard_home_header.html', context)

def load_backup(filename, content):
    prefix = 'phone_dashboard_backup_' + settings.ALLOWED_HOSTS[0]

    if filename.startswith(prefix) is False:
        return

    if 'json-dumpdata' in filename:
        filename = filename.replace('.json-dumpdata.bz2.encrypted', '.json')

        path = os.path.join(tempfile.gettempdir(), filename)

        with open(path, 'wb') as fixture_file:
            fixture_file.write(content)

        management.call_command('loaddata', path)

        os.remove(path)
    elif 'pd-bundle' in filename:
        bundle = DataBundle(recorded=timezone.now())

        if install_supports_jsonfield():
            bundle.properties = json.loads(content)
        else:
            bundle.properties = content

        bundle.save()
    else:
        print('[phone_dashboard.pdk_api.load_backup] Unknown file type: ' + filename)

def incremental_backup(parameters): # pylint: disable=too-many-locals, too-many-statements
    to_transmit = []
    to_clear = []

    prefix = 'phone_dashboard_backup_' + settings.ALLOWED_HOSTS[0]

    if 'start_date' in parameters:
        prefix += '_' + parameters['start_date'].date().isoformat()

    if 'end_date' in parameters:
        prefix += '_' + (parameters['end_date'].date() - datetime.timedelta(days=1)).isoformat()

    dumpdata_apps = (
        'study_support.AppCode',
        'study_support.AppPackageInfo',
        'study_support.AppVersion',
        'study_support.Participant',
        'study_support.TreatmentPhase',
    )

    backup_staging = tempfile.gettempdir()

    try:
        backup_staging = settings.PDK_BACKUP_STAGING_DESTINATION
    except AttributeError:
        pass

    for app in dumpdata_apps:
        print('[phone_dashboard] Backing up ' + app + '...')
        sys.stdout.flush()

        buf = io.StringIO()
        management.call_command('dumpdata', app, stdout=buf)
        buf.seek(0)

        database_dump = buf.read()

        buf = None

        gc.collect()

        compressed_str = bz2.compress(database_dump)

        database_dump = None

        gc.collect()

        filename = prefix + '_' + slugify(app) + '.json-dumpdata.bz2'

        path = os.path.join(backup_staging, filename)

        with open(path, 'wb') as fixture_file:
            fixture_file.write(compressed_str)

        to_transmit.append(path)

    # Using parameters, only backup matching DataPoint objects. Add PKs to to_clear for
    # optional deletion.

    bundle_size = 500

    try:
        bundle_size = settings.PDK_BACKUP_BUNDLE_SIZE
    except AttributeError:
        print('Define PDK_BACKUP_BUNDLE_SIZE in the settings to define the size of backup payloads.')

    app_snooze = DataGeneratorDefinition.definition_for_identifier('app-snooze')
    daily_app_budget = DataGeneratorDefinition.definition_for_identifier('daily-app-budget')
    full_app_budgets = DataGeneratorDefinition.definition_for_identifier('full-app-budgets')
    nyu_relaunch_email = DataGeneratorDefinition.definition_for_identifier('nyu-relaunch-email')

    query = Q(generator_definition=app_snooze) | Q(generator_definition=daily_app_budget) | Q(generator_definition=full_app_budgets) | Q(generator_definition=nyu_relaunch_email) # pylint: disable=unsupported-binary-operation

    if 'start_date' in parameters:
        query = query & Q(recorded__gte=parameters['start_date'])

    if 'end_date' in parameters:
        query = query & Q(recorded__lt=parameters['end_date'])

    clear_archived = False

    if 'clear_archived' in parameters and parameters['clear_archived']:
        clear_archived = True

    print('[phone_dashboard] Fetching count of data points...')
    sys.stdout.flush()

    count = DataPoint.objects.filter(query).count()

    index = 0

    while index < count:
        filename = prefix + '_data_points_' + str(index) + '_' + str(count) + '.nyu-pd-bundle.bz2'

        print('[phone_dashboard] Backing up data points ' + str(index) + ' of ' + str(count) + '...')
        sys.stdout.flush()

        bundle = []

        for point in DataPoint.objects.filter(query).order_by('recorded')[index:(index + bundle_size)]:
            bundle.append(point.fetch_properties())

            if clear_archived:
                to_clear.append('phone_dashboard:' + str(point.pk))

        index += bundle_size

        compressed_str = bz2.compress(json.dumps(bundle))

        path = os.path.join(backup_staging, filename)

        with open(path, 'wb') as compressed_file:
            compressed_file.write(compressed_str)

        to_transmit.append(path)

    return to_transmit, to_clear

def clear_points(to_clear):
    point_count = len(to_clear)

    for i in range(0, point_count):
        if (i % 1000) == 0:
            print('[phone_dashboard] Clearing points ' + str(i) + ' of ' + str(point_count) + '...')
            sys.stdout.flush()

        point_id = to_clear[i]

        point_pk = int(point_id.replace('phone_dashboard:', ''))

        DataPoint.objects.filter(pk=point_pk).delete()

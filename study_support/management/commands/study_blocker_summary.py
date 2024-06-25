# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import datetime
import json

import arrow
import pytz

from django.core.management.base import BaseCommand
from django.utils import timezone

from passive_data_kit.models import DataSourceReference, DataGeneratorDefinition, DataPoint, DeviceIssue, DataSource, Device, DeviceModel

from ...models import Participant

# Phone Dashboard/34 Passive Data Kit/1.0 (Android 8.0.0 SDK 26; samsung SM-J737U)

def platform_for_user_agent(user_agent):
    while user_agent[0] != '(':
        user_agent = user_agent[1:]

    user_agent = user_agent[1:]

    while user_agent[-1] != ';':
        user_agent = user_agent[:-1]

    user_agent = user_agent[:-1]

    return user_agent

def app_for_user_agent(user_agent):
    tokens = user_agent.split('/')

    return tokens[0]

def version_for_user_agent(user_agent):
    tokens = user_agent.split('/')

    app_tokens = tokens[1].split(' ')

    return app_tokens[0]

def device_model_for_user_agent(user_agent):
    tokens = user_agent.split(';')

    app_tokens = tokens[1][:-1].strip()

    return app_tokens

def fetch_device(source, platform, device_model):
    model = DeviceModel.objects.filter(model__iexact=device_model).first()

    if model is None:
        model = DeviceModel(model=device_model, manufacturer='Unknown')
        model.save()

    device = Device.objects.filter(source=source, platform=platform, model=model).first()

    if device is None:
        device = Device(source=source, platform=platform, model=model)
        device.save()

    return device

class Command(BaseCommand):
    help = 'Prints participant app usage in minutes on a given date.'

    def add_arguments(self, parser):
        parser.add_argument('--date',
                            type=str,
                            dest='date',
                            required=True,
                            help='Date of app usage in YYY-MM-DD format')

        parser.add_argument('--record-issue',
                            action='store_true',
                            dest='record_issue',
                            default=False,
                            help='Records device issue for identified issues')

    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        foreground_definition = DataGeneratorDefinition.definition_for_identifier('pdk-foreground-application')
        budget_definition = DataGeneratorDefinition.definition_for_identifier('full-app-budgets')
        event_definition = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

        fetch_start_date = arrow.get(options['date'] + 'T00:00:00+00:00')
        fetch_end_date = arrow.get(options['date'] + 'T23:59:59+00:00')

        print(options['date'])

        sources_refs = list(DataPoint.objects.filter(created__gte=fetch_start_date.datetime, created__lt=fetch_end_date.datetime).values_list('source_reference', flat=True).distinct().order_by())

        successful = 0

        for source_ref_id in sources_refs: # pylint: disable=too-many-nested-blocks
            source_reference = DataSourceReference.objects.get(pk=source_ref_id)

            participant = Participant.objects.filter(identifier=source_reference.source).first()

            # print('PART: ' + str(participant) + ' FROM ' + source_reference.source)

            if participant is not None:

                tz_point = DataPoint.objects.filter(source_reference=source_reference, created__lte=fetch_end_date.datetime).order_by('-created').first()

                if tz_point is not None:
                    properties = tz_point.fetch_properties()

                    if 'timezone' in properties['passive-data-metadata']:
                        my_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])
                        user_agent = tz_point.fetch_user_agent()

                        start_date = my_tz.localize(datetime.datetime(fetch_start_date.year, fetch_start_date.month, fetch_start_date.day, 0, 0, 0, 0))
                        end_date = start_date + datetime.timedelta(days=1)

                        blocker = participant.phases.filter(start_date__lte=start_date.date()).exclude(blocker_type='none').order_by('-start_date').first()

                        # print 'start_date: ' + start_date.isoformat()
                        # print 'end_date: ' + end_date.isoformat()

                        blocks = list(DataPoint.objects.filter(source_reference=source_reference, generator_definition=event_definition, secondary_identifier='blocked_app', created__gte=start_date, created__lt=end_date))

                        budget = DataPoint.objects.filter(source_reference=source_reference, generator_definition=budget_definition).order_by('-created').first()

                        if budget is not None:
                            budgets = sorted(budget.fetch_properties()['budgets'], key=lambda budget_item: budget_item['effective_on'], reverse=True)

                            day_start = arrow.get(start_date).timestamp * 1000

                            budget_item = None

                            for item in budgets:
                                if budget_item is None and day_start >= item['effective_on']:
                                    budget_item = item

                            if budget_item is not None:
                                limits = json.loads(budget_item['budget'])

                                for app in limits:
                                    app_limit = limits[app]

                                    if app_limit >= 0:
                                        last_usage = None

                                        on_sum = 0
                                        off_sum = 0

                                        dupe_count = 0

                                        for app_use in DataPoint.objects.filter(source_reference=source_reference, generator_definition=foreground_definition, secondary_identifier=app, created__gte=start_date, created__lt=end_date).order_by('created'):
                                            app_properties = app_use.fetch_properties()

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
                                            block_count = 0

                                            for block in blocks:
                                                block_payload = block.fetch_properties()

                                                if 'app' in block_payload['event_details'] and block_payload['event_details']['app'] == app:
                                                    block_count += 1

                                            if block_count > 0 and blocker is None:
                                                print(' [!] %s [%s] unnecessary block detected - blocker disabled' % (source_reference, app))

                                                if options['record_issue']:
                                                    issue = DeviceIssue()
                                                    issue.created = start_date
                                                    issue.last_updated = timezone.now()
                                                    issue.user_agent = user_agent

                                                    issue.platform = platform_for_user_agent(user_agent)
                                                    issue.app = app_for_user_agent(user_agent)
                                                    issue.version = version_for_user_agent(user_agent)
                                                    issue.device_model = device_model_for_user_agent(user_agent)

                                                    issue.device = fetch_device(DataSource.objects.get(identifier=source_reference.source), issue.platform, issue.device_model)

                                                    issue.correctness_related = True

                                                    issue.tags = app + ' pd-blocks pd-extra-block-when-disabled'
                                                    issue.description = app + ' blocked when blocker disabled'

                                                    issue.save()

                                            if blocker is not None:
                                                if on_sum < app_limit:
                                                    if block_count > 0:
                                                        print(' [ ] %s[%s] under limit: %s < %s (%s / %s overlapping usages)' % (source_reference, app, on_sum, app_limit, user_agent, dupe_count))
                                                        print(' [!] %s[%s] unnecessary block detected' %(source_reference, app))

                                                        if options['record_issue']:
                                                            issue = DeviceIssue()
                                                            issue.created = start_date
                                                            issue.last_updated = timezone.now()
                                                            issue.user_agent = user_agent

                                                            issue.platform = platform_for_user_agent(user_agent)
                                                            issue.app = app_for_user_agent(user_agent)
                                                            issue.version = version_for_user_agent(user_agent)
                                                            issue.device_model = device_model_for_user_agent(user_agent)

                                                            issue.device = fetch_device(DataSource.objects.get(identifier=source_reference.source), issue.platform, issue.device_model)

                                                            issue.correctness_related = True

                                                            issue.tags = app + ' pd-blocks pd-extra-block pd-blocker' + blocker.blocker_type
                                                            issue.description = app + ' under limit: ' + str(on_sum) + ' < ' + str(app_limit) + ' (' + str(dupe_count) + ' overlapping usages)'

                                                            issue.save()
                                                    else:
                                                        successful += 1

                                                        if options['record_issue']:
                                                            issue = DeviceIssue()
                                                            issue.created = start_date
                                                            issue.last_updated = timezone.now()
                                                            issue.user_agent = user_agent

                                                            issue.platform = platform_for_user_agent(user_agent)
                                                            issue.app = app_for_user_agent(user_agent)
                                                            issue.version = version_for_user_agent(user_agent)
                                                            issue.device_model = device_model_for_user_agent(user_agent)

                                                            issue.device = fetch_device(DataSource.objects.get(identifier=source_reference.source), issue.platform, issue.device_model)

                                                            issue.correctness_related = True

                                                            issue.tags = app + ' pd-blocks pd-nonblock-ok pd-blocker' + blocker.blocker_type
                                                            issue.description = app + ' non-block ok: ' + str(on_sum) + ' < ' + str(app_limit) + ' (' + str(dupe_count) + ' overlapping usages)'

                                                            issue.save()
                                                else:
                                                    # print '[X] ' + str(source_reference) + '[' + app + '] over limit: ' + str(on_sum) + ' > ' + str(app_limit) + ' (' + user_agent + ' / ' + str(dupe_count) + ' overlapping usages)'

                                                    if block_count > 0:
                                                        successful += 1

                                                        if options['record_issue']:
                                                            issue = DeviceIssue()
                                                            issue.created = start_date
                                                            issue.last_updated = timezone.now()
                                                            issue.user_agent = user_agent

                                                            issue.platform = platform_for_user_agent(user_agent)
                                                            issue.app = app_for_user_agent(user_agent)
                                                            issue.version = version_for_user_agent(user_agent)
                                                            issue.device_model = device_model_for_user_agent(user_agent)

                                                            issue.device = fetch_device(DataSource.objects.get(identifier=source_reference.source), issue.platform, issue.device_model)

                                                            issue.correctness_related = True

                                                            issue.tags = app + ' pd-blocks pd-block-ok pd-blocker' + blocker.blocker_type
                                                            issue.description = app + ' block ok: ' + str(on_sum) + ' > ' + str(app_limit) + ' (' + str(dupe_count) + ' overlapping usages)'

                                                            issue.save()
                                                    else:
                                                        print('[X] %s[%s] over limit: %s > %s (%s / %s overlapping usages)' % (source_reference, app, on_sum, app_limit, user_agent, dupe_count))
                                                        print(' [!] %s[%s] block missing' % (source_reference, app))

                                                        if options['record_issue']:
                                                            issue = DeviceIssue()
                                                            issue.created = start_date
                                                            issue.last_updated = timezone.now()
                                                            issue.user_agent = user_agent

                                                            issue.platform = platform_for_user_agent(user_agent)
                                                            issue.app = app_for_user_agent(user_agent)
                                                            issue.version = version_for_user_agent(user_agent)
                                                            issue.device_model = device_model_for_user_agent(user_agent)

                                                            issue.device = fetch_device(DataSource.objects.get(identifier=source_reference.source), issue.platform, issue.device_model)

                                                            issue.correctness_related = True

                                                            issue.tags = app + ' pd-blocks pd-missing-block pd-blocker' + blocker.blocker_type
                                                            issue.description = app + ' over limit: ' + str(on_sum) + ' > ' + str(app_limit) + ' (' + str(dupe_count) + ' overlapping usages)'

                                                            issue.save()

                            else:
                                pass # print '[!] No budget saved for ' + str(source_reference)
                        else:
                            pass # print '[!] No budget data transmitted for ' + str(source_reference)

        print('SUCCESSFUL: %s' %successful)

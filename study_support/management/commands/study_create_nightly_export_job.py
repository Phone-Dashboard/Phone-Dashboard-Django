# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import datetime

import arrow

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from passive_data_kit.decorators import handle_lock
from passive_data_kit.models import ReportJobBatchRequest, DataSource, DataPoint, DataServerMetadatum, LATEST_POINT_DATUM

class Command(BaseCommand):
    help = 'Creates a nightly job to upload data to Dropbox.'

    def add_arguments(self, parser):
        parser.add_argument('--date',
                            type=str,
                            dest='date',
                            help='Date of app usage in YYY-MM-DD format')

        parser.add_argument('--include-all',
                            dest='include_all',
                            action='store_true',
                            help='Include all data, ignoring data alerting settings')

        parser.add_argument('--suppress-full-export',
                            dest='suppress_full',
                            action='store_true',
                            help='Skip nyu-full-export')

        parser.add_argument('--suppress-snooze',
                            dest='suppress_snooze',
                            action='store_true',
                            help='Skip nyu-snooze-warnings')

        parser.add_argument('--suppress-budgets',
                            dest='suppress_budgets',
                            action='store_true',
                            help='Skip nyu-app-budgets')

        parser.add_argument('--suppress-events',
                            dest='suppress_events',
                            action='store_true',
                            help='Skip nyu-snooze-events')

        parser.add_argument('--suppress-status',
                            dest='suppress_status',
                            action='store_true',
                            help='Skip nyu-participant-status')

        parser.add_argument('--suppress-app-usages',
                            dest='suppress_app_usages',
                            action='store_true',
                            help='Skip nyu-latest-usage-summaries')

        parser.add_argument('--suppress-snooze-delays',
                            dest='suppress_snooze_delays',
                            action='store_true',
                            help='Skip nyu-snooze-delays')

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        now = timezone.now()

        if options['date'] is not None:
            now = arrow.get(options['date'] + 'T23:59:59+00:00').datetime

        requester = get_user_model().objects.get(username='dropbox_user')

        yesterday = now.date() - datetime.timedelta(days=1)

        twenty_ago = now.date() - datetime.timedelta(days=20)

        # parameters = {}
        # parameters['sources'] = []

        # for source in DataSource.objects.all():
        #     parameters['sources'].append(source.identifier)

        # parameters['generators'] = ['nyu-daily-usage-summary']
        # parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
        # parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
        # parameters['date_type'] = 'recorded'
        # parameters['export_raw'] = False
        # parameters['prefix'] = 'nyu_daily_usage_summary'

        # request = ReportJobBatchRequest(requester=requester, requested=now + datetime.timedelta(seconds=60), parameters=parameters)
        # request.save()

        cut_off = timezone.now() - datetime.timedelta(days=14)

        active_users = []

        for source in DataSource.objects.all().order_by('identifier'):
            key = LATEST_POINT_DATUM + ': ' + source.identifier + '/pdk-data-frequency'

            latest_point_datum = DataServerMetadatum.objects.filter(key=key).first()

            point = None

            if latest_point_datum is not None:
                point = DataPoint.objects.filter(pk=int(latest_point_datum.value)).first()

            if point is not None and point.created > cut_off:
                if (source.identifier in active_users) is False:
                    if options['include_all'] or source.should_suppress_alerts() is False:
                        active_users.append(source.identifier)

        if options['suppress_snooze_delays'] is not True:
            parameters = {}
            parameters['sources'] = active_users

            parameters['generators'] = ['nyu-snooze-delays']
            parameters['export_raw'] = False
            parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
            parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
            parameters['date_type'] = 'recorded'
            parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_snooze_delays'
            parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

            request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
            request.save()


        if options['suppress_snooze'] is not True:
            parameters = {}
            parameters['sources'] = active_users

            parameters['generators'] = ['nyu-snooze-warnings']
            parameters['export_raw'] = False
            parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
            parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
            parameters['date_type'] = 'recorded'
            parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_snooze_warnings'
            parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

            request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
            request.save()

        if options['suppress_budgets'] is not True:
            parameters = {}
            parameters['sources'] = active_users

            parameters['generators'] = ['nyu-app-budgets']
            parameters['export_raw'] = False
            parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
            parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
            parameters['date_type'] = 'recorded'
            parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_app_budgets'
            parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

            request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
            request.save()

        # if options['suppress_events'] is not True:
        #    parameters = {}
        #    parameters['sources'] = []

        #    for source in DataSource.objects.all():
        #        if options['include_all'] or source.should_suppress_alerts() is False:
        #            parameters['sources'].append(source.identifier)

        #    parameters['generators'] = ['nyu-snooze-events']
        #    parameters['export_raw'] = False
        #    parameters['data_start'] = None
        #    parameters['data_end'] = None
        #    parameters['date_type'] = 'recorded'
        #    parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_snooze_events'
        #    parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

        #    request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
        #    request.save()

        # parameters = {}
        # parameters['sources'] = []

        # for source in DataSource.objects.all():
        #     parameters['sources'].append(source.identifier)

        # parameters['generators'] = ['pdk-web-visit']
        # parameters['export_raw'] = False
        # parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
        # parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
        # parameters['date_type'] = 'recorded'
        # parameters['prefix'] = 'pdk_web_visit'

        # request = ReportJobBatchRequest(requester=requester, requested=(now + datetime.timedelta(seconds=300)), parameters=parameters)
        # request.save()

        if options['suppress_status'] is not True:
            parameters = {}
            parameters['sources'] = active_users

            parameters['generators'] = ['nyu-participant-status']
            parameters['export_raw'] = False
            parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
            parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
            parameters['date_type'] = 'recorded'
            parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_participant_status'
            parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

            request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
            request.save()

        if options['suppress_app_usages'] is not True:
            parameters = {}
            parameters['sources'] = active_users

            parameters['generators'] = ['nyu-latest-usage-summaries']
            parameters['export_raw'] = False
            parameters['data_start'] = twenty_ago.strftime('%m/%d/%Y')
            parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
            parameters['date_type'] = 'recorded'
            parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_alternative'
            parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

            request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
            request.save()

        if options['suppress_full'] is not True:
            parameters = {}
            parameters['sources'] = active_users

            parameters['generators'] = ['nyu-full-export']
            parameters['data_start'] = yesterday.strftime('%m/%d/%Y')
            parameters['data_end'] = yesterday.strftime('%m/%d/%Y')
            parameters['date_type'] = 'recorded'
            parameters['export_raw'] = False
            parameters['prefix'] = yesterday.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_nyu_use_export'
            parameters['suffix'] = yesterday.strftime('%Y-%m-%d')

            request = ReportJobBatchRequest(requester=requester, requested=now, parameters=parameters)
            request.save()

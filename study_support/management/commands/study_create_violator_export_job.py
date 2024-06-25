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
    help = 'Creates a 12 hour job to upload violator data to Dropbox.'

    def add_arguments(self, parser):
        parser.add_argument('--date',
                            type=str,
                            dest='date',
                            help='Date of app usage in YYY-MM-DD format')

        parser.add_argument('--include-all',
                            dest='include_all',
                            action='store_true',
                            help='Include all data, ignoring data alering settings')

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        now = timezone.now().date()

        if options['date'] is not None:
            now = arrow.get(options['date'] + 'T23:59:59+00:00').datetime

        requester = get_user_model().objects.get(username='dropbox2')

        parameters = {}
        parameters['sources'] = []

        cut_off = timezone.now() - datetime.timedelta(days=14)

        for source in DataSource.objects.all().order_by('identifier'):
            key = LATEST_POINT_DATUM + ': ' + source.identifier + '/pdk-data-frequency'

            latest_point_datum = DataServerMetadatum.objects.filter(key=key).first()

            point = None

            if latest_point_datum is not None:
                point = DataPoint.objects.filter(pk=int(latest_point_datum.value)).first()

            if point is not None and point.created > cut_off:
                if (source.identifier in parameters['sources']) is False and (options['include_all'] or source.should_suppress_alerts() is False):
                    parameters['sources'].append(source.identifier)

        parameters['generators'] = ['nyu-violator-usage']
        parameters['data_start'] = now.strftime('%m/%d/%Y')
        parameters['data_end'] = now.strftime('%m/%d/%Y')
        parameters['date_type'] = 'recorded'
        parameters['export_raw'] = False
        parameters['prefix'] = now.strftime('%Y-%m-%d') + '_' + settings.PD_HOST_REPORT_PREFIX + '_pd-bad-use'
        parameters['suffix'] = now.strftime('%Y-%m-%d')

        request = ReportJobBatchRequest(requester=requester, requested=timezone.now(), parameters=parameters)
        request.save()

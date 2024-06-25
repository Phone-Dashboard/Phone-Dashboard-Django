# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from passive_data_kit.models import DataSource, DataPoint, LATEST_POINT_DATUM, DataServerMetadatum

class Command(BaseCommand):
    help = 'Lists identifiers of sources contributing data in the last week'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        cut_off = timezone.now() - datetime.timedelta(days=7)

        for source in DataSource.objects.all().order_by('identifier'):
            key = LATEST_POINT_DATUM + ': ' + source.identifier + '/pdk-data-frequency'

            latest_point_datum = DataServerMetadatum.objects.filter(key=key).first()

            point = None

            if latest_point_datum is not None:
                point = DataPoint.objects.filter(pk=int(latest_point_datum.value)).first()

            if point is not None and point.created > cut_off:
                print('%s: %s' % (source.identifier, point.created.date().isoformat()))

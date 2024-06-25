# pylint: disable=no-member,line-too-long
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from passive_data_kit.models import DataSourceReference, DataGeneratorDefinition, DataPoint

class Command(BaseCommand):
    help = 'Prints participant disk usage information.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        status_def = DataGeneratorDefinition.definition_for_identifier('pdk-system-status')

        for source_reference in DataSourceReference.objects.order_by('source').all():
            last_status = DataPoint.objects.filter(source_reference=source_reference, generator_definition=status_def).order_by('-created').first()

            if last_status is not None:
                properties = last_status.fetch_properties()

                storage_available = properties['storage_available']
                storage_other = properties['storage_other']
                storage_total = properties['storage_total']
                storage_app = properties['storage_app']

                row = []

                row.append(source_reference.source)
                row.append(last_status.created.isoformat())
                row.append('%.3f' % (float(storage_total) / (1024 * 1024 * 1024)))
                row.append('%.3f' % (float(storage_app) / (1024 * 1024 * 1024)))
                row.append('%.3f' % (float(storage_app) / float(storage_total)))
                row.append('%.3f' % (float(storage_other) / (1024 * 1024 * 1024)))
                row.append('%.3f' % (float(storage_other) / float(storage_total)))
                row.append('%.3f' % (float(storage_available) / (1024 * 1024 * 1024)))
                row.append('%.3f' % (float(storage_available) / float(storage_total)))

                print('\t'.join(row))

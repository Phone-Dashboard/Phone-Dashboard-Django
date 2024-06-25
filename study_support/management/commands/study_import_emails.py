# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import csv

from django.core.management.base import BaseCommand

from passive_data_kit.decorators import handle_lock

from ...models import Participant

class Command(BaseCommand):
    help = 'Imports e-mails from CSV file and associates them with participant records'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', nargs=1, type=str)

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        print('%s' % options)

        for csv_file in options['csv_file']:
            with open(csv_file, 'rb') as csvfile:
                reader = csv.reader(csvfile, delimiter=',')

                for row in reader:
                    for participant in Participant.objects.filter(identifier=row[0]):
                        participant.email_address = row[1]
                        participant.save()

                        print('Updated %s.' % participant.identifier)

# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from passive_data_kit.decorators import handle_lock
from passive_data_kit.models import DataSource, DataSourceGroup

from ...models import Participant

class Command(BaseCommand):
    help = 'Creates participants ahead of typical enrollment process.'

    def add_arguments(self, parser):
        parser.add_argument('--count',
                            type=int,
                            dest='count',
                            default=1,
                            help='Number of times to repeat in a single run')

        parser.add_argument('--group',
                            type=str,
                            dest='group',
                            default='Batch-Created Participants',
                            help='Name of group that participants join.')

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        group = DataSourceGroup.objects.filter(name=options['group']).first()

        if group is None:
            group = DataSourceGroup(name=options['group'])
            group.save()

        created = 0

        while created < options['count']:
            identifier = Participant.unique_identifier()

            email = identifier + '@' + settings.ALLOWED_HOSTS[0]

            print(email)

            participant = Participant(email_address=email)
            participant.created = timezone.now()
            participant.generate_identifier(use_identifier=identifier)
            participant.save()

            call_command('study_seed_participants')

            data_source = DataSource.objects.get(identifier=participant.identifier)
            data_source.group = group
            data_source.name = email

            data_source.save()

            created += 1

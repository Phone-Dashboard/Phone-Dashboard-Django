# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

from django.core.management.base import BaseCommand
from django.utils import timezone

from passive_data_kit.decorators import handle_lock
from passive_data_kit.models import DataSource, DataSourceGroup

from ...models import Participant

class Command(BaseCommand):
    help = 'Creates PDK data sources for unattached Participant objects.'

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        default_group = DataSourceGroup.objects.order_by('name').first()

        for participant in Participant.objects.all():
            data_source = DataSource.objects.filter(identifier=participant.identifier).first()

            if data_source is None:
                data_source = DataSource(identifier=participant.identifier)
                data_source.group = default_group
                data_source.name = participant.identifier
                data_source.save()

        for data_source in DataSource.objects.all():
            participant = Participant.objects.filter(identifier=data_source.identifier).first()

            if participant is None:
                participant = Participant(identifier=data_source.identifier)
                participant.created = timezone.now()
                participant.email_address = data_source.identifier + '@example.com'

                participant.save()

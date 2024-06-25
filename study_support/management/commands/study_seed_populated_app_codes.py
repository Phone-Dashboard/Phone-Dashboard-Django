# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

from django.core.management.base import BaseCommand

from passive_data_kit.decorators import handle_lock

from ...models import Participant, AppCode

class Command(BaseCommand):
    help = 'Populates the app code pool with existing app codes.'

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        for participant in Participant.objects.all():
            app_code = AppCode.objects.filter(identifier=participant.identifier).first()

            if app_code is None:
                app_code = AppCode(identifier=participant.identifier, claimed=True)
                app_code.save()

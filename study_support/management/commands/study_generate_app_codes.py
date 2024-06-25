# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import json
import random

from django.core.management.base import BaseCommand

from passive_data_kit.decorators import handle_lock
from passive_data_kit.models import DataServer

from ...models import AppCode

class Command(BaseCommand):
    help = 'Generates new unused app codes.'

    def add_arguments(self, parser):
        parser.add_argument('--count',
                            type=int,
                            dest='count',
                            default=50,
                            help='Number of new app codes to generate')

    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        valid_characters = '987654321'

        generated = 0

        servers = list(DataServer.objects.all())

        while generated < options['count']:
            identifier_exists = True

            identifier = ''

            while identifier_exists:
                identifier = ''.join(random.SystemRandom().choice(valid_characters) for _ in range(8))

                identifier_exists = (AppCode.objects.filter(identifier=identifier).count() > 0) # pylint: disable=superfluous-parens

            configuration = {}
            configuration['server'] = servers[generated % len(servers)].name

            app_code = AppCode(identifier=identifier, claimed=False, configuration=json.dumps(configuration, indent=2))
            app_code.save()

            generated += 1

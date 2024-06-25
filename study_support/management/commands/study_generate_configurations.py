# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

import copy
import json

from django.core.management.base import BaseCommand

from passive_data_kit.decorators import handle_lock
from passive_data_kit.models import DataSource, AppConfiguration, install_supports_jsonfield

class Command(BaseCommand):
    help = 'Creates PDK configurations for individual devices.'

    @handle_lock
    def handle(self, *args, **options):
        base_config = {
            'transmitters': [{
                'upload-uri': 'https://phone-dashboard.audacious-software.com/data/add-bundle.json',
                'use-external-storage': True,
                'compression': True,
                'server-key': 'DJQmDZlJ6L+PW0omE4mM5kKXl9i36rd+EspXPbnbYgE=',
                'strict-ssl-verification': True,
                'identifier': 'pdk-http-transmitter',
                'type': 'pdk-http-transmitter',
                'charging-only': False,
                'device-key': 'oJUJqZ8oQGGrj4+JB9JVOH/4fp9JmVLiD0bQX0Ow+6Q=',
                'wifi-only': False
            }],
            'validated': True,
            'generators': [{
                'identifier': 'pdk-screen-state'
            }, {
                'identifier': 'pdk-foreground-application',
                'sample-interval': 5000
            }, {
                'identifier': 'pdk-system-status'
            }],
            'name': 'Phone Dashboard'
        }

        for source in DataSource.objects.all():
            if source.server is not None:
                config = AppConfiguration.objects.filter(id_pattern=source.identifier).first()

                if config is None:
                    config = AppConfiguration(id_pattern=source.identifier, context_pattern='.*', evaluate_order=1, is_valid=True, is_enabled=True)

                    custom_config = copy.deepcopy(base_config)

                    custom_config['transmitters'][0]['upload-uri'] = source.server.upload_url
                    config.name = source.identifier + ' Configuration'

                    if install_supports_jsonfield():
                        config.configuration_json = custom_config
                    else:
                        config.configuration_json = json.dumps(custom_config, indent=2)

                    config.save()

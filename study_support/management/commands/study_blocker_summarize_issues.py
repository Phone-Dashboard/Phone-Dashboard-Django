# -*- coding: utf-8 -*-
# pylint: disable=no-member,line-too-long

from django.core.management.base import BaseCommand

from passive_data_kit.models import DataSourceReference, DeviceIssue, DataSource, Device, DeviceModel

class Command(BaseCommand):
    help = 'Prints participant app usage in minutes on a given date.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options): # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        issues = DeviceIssue.objects.filter(tags__icontains='pd-blocks')

        # By Platform
        platforms = list(Device.objects.all().values_list('platform', flat=True).distinct().order_by())

        print('Issues by Platform')
        print('Platform\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        for platform in platforms:
            no_block_success = 0
            block_success = 0

            missing_block = 0
            extra_block = 0

            for device in Device.objects.filter(platform=platform):
                for issue in issues.filter(device=device):
                    if 'pd-nonblock-ok' in issue.tags:
                        no_block_success += 1
                    elif 'pd-block-ok' in issue.tags:
                        block_success += 1
                    elif 'pd-extra-block' in issue.tags:
                        extra_block += 1
                    elif 'pd-missing-block' in issue.tags:
                        missing_block += 1

            print('%s\t%s\t%s\t%s\t%s' % (platform, no_block_success, block_success, extra_block, missing_block))

        # By Model

        print('Issues by Model')
        print('Model\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        for model in DeviceModel.objects.all():
            no_block_success = 0
            block_success = 0

            missing_block = 0
            extra_block = 0

            for device in Device.objects.filter(model=model):
                for issue in issues.filter(device=device):
                    if 'pd-nonblock-ok' in issue.tags:
                        no_block_success += 1
                    elif 'pd-block-ok' in issue.tags:
                        block_success += 1
                    elif 'pd-extra-block' in issue.tags:
                        extra_block += 1
                    elif 'pd-missing-block' in issue.tags:
                        missing_block += 1

            print('%s\t%s\t%s\t%s\t%s' % (model.model, no_block_success, block_success, extra_block, missing_block))

        # By Version

        versions = list(DeviceIssue.objects.all().values_list('version', flat=True).distinct().order_by())

        print('Issues by Version')
        print('Version\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        for version in versions:
            no_block_success = 0
            block_success = 0

            missing_block = 0
            extra_block = 0

            for issue in issues.filter(version=version):
                if 'pd-nonblock-ok' in issue.tags:
                    no_block_success += 1
                elif 'pd-block-ok' in issue.tags:
                    block_success += 1
                elif 'pd-extra-block' in issue.tags:
                    extra_block += 1
                elif 'pd-missing-block' in issue.tags:
                    missing_block += 1

            print('%s\t%s\t%s\t%s\t%s' % (version, no_block_success, block_success, extra_block, missing_block))

        # By source
        print('Issues by Source')
        print('Source\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        for source_ref in DataSourceReference.objects.all():
            source = DataSource.objects.filter(identifier=source_ref.source).first()

            if source is not None:
                no_block_success = 0
                block_success = 0

                missing_block = 0
                extra_block = 0

                for device in Device.objects.filter(source=source):
                    for issue in issues.filter(device=device):
                        if 'pd-nonblock-ok' in issue.tags:
                            no_block_success += 1
                        elif 'pd-block-ok' in issue.tags:
                            block_success += 1
                        elif 'pd-extra-block' in issue.tags:
                            extra_block += 1
                        elif 'pd-missing-block' in issue.tags:
                            missing_block += 1

                if (no_block_success + block_success + missing_block + extra_block) > 0:
                    print('%s\t%s\t%s\t%s\t%s' % (source_ref.source, no_block_success, block_success, extra_block, missing_block))

        # By Model/Platform

        print('Issues by Model/Platform')
        print('Model\tPlatform\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        for model in DeviceModel.objects.all():
            platforms = []

            for device in Device.objects.filter(model=model):
                if (device.platform in platforms) is False:
                    platforms.append(device.platform)

            for platform in platforms:
                no_block_success = 0
                block_success = 0

                missing_block = 0
                extra_block = 0

                for device in Device.objects.filter(model=model, platform=platform):
                    for issue in issues.filter(device=device):
                        if 'pd-nonblock-ok' in issue.tags:
                            no_block_success += 1
                        elif 'pd-block-ok' in issue.tags:
                            block_success += 1
                        elif 'pd-extra-block' in issue.tags:
                            extra_block += 1
                        elif 'pd-missing-block' in issue.tags:
                            missing_block += 1

                print('%s\t%s\t%s\t%s\t%s\t%s' % (model.model, platform, no_block_success, block_success, extra_block, missing_block))

        print('Issues by App')
        print('App\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        apps = {}

        for issue in DeviceIssue.objects.filter(tags__icontains='pd-blocks'):
            app = issue.tags.replace('pd-blocks', '').replace('pd-nonblock-ok', '').replace('pd-block-ok', '').replace('pd-extra-block', '').replace('pd-missing-block', '').strip()

            if (app in apps) is False:
                apps[app] = {
                    'pd-nonblock-ok': 0,
                    'pd-block-ok': 0,
                    'pd-extra-block': 0,
                    'pd-missing-block': 0,
                }

            if 'pd-nonblock-ok' in issue.tags:
                apps[app]['pd-nonblock-ok'] += 1
            elif 'pd-block-ok' in issue.tags:
                apps[app]['pd-block-ok'] += 1
            elif 'pd-extra-block' in issue.tags:
                apps[app]['pd-extra-block'] += 1
            elif 'pd-missing-block' in issue.tags:
                apps[app]['pd-missing-block'] += 1

        for (key, item) in apps.items():
            print('%s\t%s\t%s\t%s\t%s' % (app, item['pd-nonblock-ok'], item['pd-block-ok'], item['pd-extra-block'], item['pd-missing-block']))

        print('Issues by App and Source')
        print('Source\tModel\tApp\tNon-Block OK\tBlock OK\tExtra Block\tMissing Block')

        for source_ref in DataSourceReference.objects.all():
            source = DataSource.objects.filter(identifier=source_ref.source).first()

            if source is not None:
                apps = {}

                last_model = None

                for device in Device.objects.filter(source=source):
                    for issue in issues.filter(device=device, tags__icontains='pd-blocks'):
                        app = issue.tags.replace('pd-blocks', '').replace('pd-nonblock-ok', '').replace('pd-block-ok', '').replace('pd-extra-block', '').replace('pd-missing-block', '').strip()

                        if (app in apps) is False:
                            apps[app] = {
                                'pd-nonblock-ok': 0,
                                'pd-block-ok': 0,
                                'pd-extra-block': 0,
                                'pd-missing-block': 0,
                            }

                        if 'pd-nonblock-ok' in issue.tags:
                            apps[app]['pd-nonblock-ok'] += 1
                        elif 'pd-block-ok' in issue.tags:
                            apps[app]['pd-block-ok'] += 1
                        elif 'pd-extra-block' in issue.tags:
                            apps[app]['pd-extra-block'] += 1
                        elif 'pd-missing-block' in issue.tags:
                            apps[app]['pd-missing-block'] += 1

                        last_model = device.model

                for (key, item) in apps.items():
                    print('%s\t%s\t%s\t%s\t%s\t%s\t%s' % (source.identifier, last_model, key, item['pd-nonblock-ok'], item['pd-block-ok'], item['pd-extra-block'], item['pd-missing-block']))

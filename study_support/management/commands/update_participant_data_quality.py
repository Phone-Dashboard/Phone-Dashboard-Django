# -*- coding: utf-8 -*-
# pylint: disable=no-member, line-too-long

import datetime
import json

from urllib.parse import urlparse

import arrow
import pytz
import requests

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from passive_data_kit.decorators import handle_lock
from passive_data_kit.models import DataSourceReference, DataGeneratorDefinition, DataPoint, DataSource

from ...models import Participant, TreatmentPhase

class Command(BaseCommand):
    @handle_lock
    def handle(self, *args, **options): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        update_participants = Participant.objects.filter(performance_last_updated=None)

        if update_participants.count() == 0:
            update_participants = Participant.objects.all().order_by('performance_last_updated')[:50]

        for update_participant in update_participants: # pylint: disable=too-many-nested-blocks
            now = timezone.now()

            full_source = DataSource.objects.filter(identifier=update_participant.identifier).first()

            metadata = json.loads(update_participant.metadata)

            performance_report = {}

            if full_source is not None:
                if full_source.server is None:
                    update_participant.fetch_timezone(force_recalculate=True)
                    update_participant.fetch_last_cost(force_recalculate=True)

                    performance_report['group'] = 'Unknown'

                    source = DataSourceReference.reference_for_source(update_participant.identifier)

                    if full_source is not None:
                        performance_report['group'] = str(full_source.group)

                    generator = DataGeneratorDefinition.definition_for_identifier('pdk-foreground-application')

                    today_start = now - datetime.timedelta(days=1)

                    yesterday_start = now - datetime.timedelta(days=2)

                    today_count = float(DataPoint.objects.filter(source_reference=source, generator_definition=generator, created__gte=today_start).count())
                    performance_report['today_observed_count'] = today_count

                    yesterday_count = float(DataPoint.objects.filter(source_reference=source, generator_definition=generator, created__gte=yesterday_start, created__lt=today_start).count())
                    performance_report['yesterday_observed_count'] = yesterday_count

                    if today_count == 0:
                        performance_report['today_observed_fraction'] = 0
                    elif yesterday_count == 0:
                        performance_report['today_observed_fraction'] = 1
                    else:
                        performance_report['today_observed_fraction'] = float(today_count) / float(yesterday_count)

                    performance_report['phase_type'] = None
                    performance_report['phase_start'] = None
                    performance_report['phase_budget'] = None
                    performance_report['phase_budget_overdue'] = False
                    performance_report['phase_snooze_cost_count'] = 0
                    performance_report['phase_snooze_cost_overdue'] = False
                    performance_report['phase_unnecessary_snooze_cost'] = False
                    performance_report['phase_snoozes'] = 0
                    performance_report['phase_misc_issues'] = []

                    latest = DataPoint.objects.filter(source_reference=source, generator_definition=generator).order_by('-created').first()

                    if latest is not None:
                        properties = latest.fetch_properties()

                        here_tz = pytz.timezone(settings.TIME_ZONE)

                        if 'timezone' in properties['passive-data-metadata']:
                            here_tz = pytz.timezone(properties['passive-data-metadata']['timezone'])

                        performance_report['latest_point'] = latest.created.astimezone(here_tz).isoformat()
                        performance_report['latest_ago'] = (now - latest.created).total_seconds() # localize to server timezone

                        if performance_report['latest_ago'] > 24 * 60 * 60:
                            update_participant.send_relaunch_email()

                        # Phone Dashboard/33 Passive Data Kit/1.0 (Android 9 SDK 28; samsung SM-G973U)

                        if latest.user_agent is not None and 'Phone Dashboard' in latest.user_agent:
                            tokens = latest.user_agent.split(' ')

                            performance_report['app_version'] = ' '.join(tokens[:2])
                            performance_report['platform_version'] = ' '.join(tokens[5:9]).replace('(', '').replace(';', '')
                            performance_report['device_model'] = ' '.join(tokens[9:]).replace(')', '')
                    else:
                        latest = DataPoint.objects.filter(source_reference=source).order_by('-created').first()

                        if latest is not None:
                            performance_report['latest_point'] = latest.created.isoformat()
                            performance_report['latest_ago'] = (now - latest.created).total_seconds() # localize to server timezone

                            if performance_report['latest_ago'] > 24 * 60 * 60:
                                update_participant.send_relaunch_email()

                    current_phase = TreatmentPhase.objects.filter(participant=update_participant, start_date__lte=now.date(), treatment_active=True).order_by('-start_date').first()

                    if current_phase is not None:
                        generator = DataGeneratorDefinition.definition_for_identifier('daily-app-budget')

                        performance_report['phase_type'] = current_phase.blocker_type
                        performance_report['phase_start'] = current_phase.start_date.isoformat()

                        latest_budget = DataPoint.objects.filter(source_reference=source, generator_definition=generator, created__date__gte=current_phase.start_date).order_by('-created').first()

                        if latest_budget is not None:
                            budget = json.loads(latest_budget.fetch_properties()['budget'])

                            if budget:
                                performance_report['phase_budget'] = budget
                        elif (now.date() - current_phase.start_date).days > 0:
                            performance_report['phase_budget_overdue'] = True

                        if current_phase.blocker_type == 'costly_snooze':
                            generator = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                            snooze_costs = DataPoint.objects.filter(source_reference=source, generator_definition=generator, secondary_identifier='set-snooze-cost', created__date__gte=current_phase.start_date).order_by('-created')

                            performance_report['phase_snooze_cost_count'] = snooze_costs.count()

                            snooze_cost = snooze_costs.first()

                            if snooze_cost is None and (now.date() - current_phase.start_date).days > 0:
                                performance_report['phase_snooze_cost_overdue'] = True
                        else:
                            generator = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                            snooze_costs = DataPoint.objects.filter(source_reference=source, generator_definition=generator, secondary_identifier='set-snooze-cost', created__date__gte=current_phase.start_date).order_by('-created')

                            performance_report['phase_snooze_cost_count'] = snooze_costs.count()

                            snooze_cost = snooze_costs.first()

                            if snooze_cost is None and (now.date() - current_phase.start_date).days > 0:
                                performance_report['phase_unnecessary_snooze_cost'] = True

                        generator = DataGeneratorDefinition.definition_for_identifier('app-snooze')

                        performance_report['phase_snoozes'] = DataPoint.objects.filter(source_reference=source, generator_definition=generator, created__date__gte=current_phase.start_date).count()

                        if performance_report['phase_snoozes'] > 0:
                            if performance_report['phase_budget'] is None or len(performance_report['phase_budget']) == 0: # pylint: disable=len-as-condition
                                performance_report['phase_misc_issues'].append('Recorded ' + str(performance_report['phase_snoozes']) + ' snooze(s) without corresponding limits being set.')

                        event_generator = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

                        use_summary = DataPoint.objects.filter(source_reference=source, generator_definition=event_generator, secondary_identifier='app-usage-summary', created__date__gte=current_phase.start_date).order_by('-created').first()

                        if use_summary is not None:
                            details = use_summary.fetch_properties()

                            if 'day' in details['event_details'] and 'blocks' in details['event_details'] and update_participant.timezone is not None:
                                report_now = arrow.Arrow.utcfromtimestamp(details['observed'] / 1000)

                                today_start = report_now.to(update_participant.timezone).replace(hour=0, minute=0, second=0).datetime
                                today_end = today_start + datetime.timedelta(days=1)

                                if performance_report['phase_budget'] is not None:
                                    for app in budget.keys():
                                        if app in details['event_details']['day']:
                                            if details['event_details']['day'][app]['usage_ms'] > budget[app]:
                                                found_block = False

                                                for block_ts in details['event_details']['blocks'].keys():
                                                    block_when = arrow.get(block_ts).datetime

                                                    if block_when >= today_start and block_when < today_end: # pylint: disable=chained-comparison
                                                        if details['event_details']['blocks'][block_ts]['app'] == app:
                                                            found_block = True

                                                if found_block is False:
                                                    issue = 'Missing block for app "' + app + '" on ' + today_start.date().isoformat() + ' (' + str(update_participant.identifier) + ').'

                                                    performance_report['phase_misc_issues'].append(issue)

                elif full_source.server.source_metadata_url is not None:
                    components = urlparse.urlsplit(full_source.server.source_metadata_url)

                    url = urlparse.urlunsplit([components.scheme, components.netloc, reverse('fetch_participant_data_quality'), '', ''])

                    payload = {
                        'identifier': update_participant.identifier,
                        'request-key': full_source.server.request_key
                    }

                    identifier_post = requests.post(url, data=payload, timeout=300)

                    if identifier_post.status_code >= 200 and identifier_post.status_code < 300:
                        response = identifier_post.json()

                        if 'study_performance_report' in response:
                            performance_report = response['study_performance_report']

                            if performance_report['latest_ago'] > 24 * 60 * 60:
                                update_participant.send_relaunch_email()
                        else:
                            print('Unable to find metadata for %s: %s' % (update_participant.identifier, json.dumps(response, indent=2)))
                    else:
                        print('Server code %s received for request for %s metadata from %s' % (identifier_post.status_code, full_source.identifier, full_source.server.source_metadata_url))

            metadata['study_performance_report'] = performance_report

            update_participant.metadata = json.dumps(metadata, indent=2)
            update_participant.performance_last_updated = now
            update_participant.save()

# pylint: disable=line-too-long,no-member
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import hashlib
import json

import arrow

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

from passive_data_kit.models import DataPoint, DataGeneratorDefinition, DataSourceReference, DataSource, DataServer

BLOCKER_TYPES = (
    ('none', 'No Blocker',),
    ('free_snooze', 'Free Snooze',),
    ('costly_snooze', 'Costly Snooze',),
    ('flexible_snooze', 'Flexible Snooze',),
    ('no_snooze', 'No Snooze',),
)

class Participant(models.Model):
    email_address = models.EmailField(unique=True, db_index=True)

    identifier = models.CharField(max_length=1024, unique=True, db_index=True)

    created = models.DateTimeField()
    performance_last_updated = models.DateTimeField(null=True, blank=True)

    email_enabled = models.BooleanField(default=True)

    metadata = models.TextField(max_length=1048576, default='{}')

    last_reminder_sent = models.DateTimeField(null=True, blank=True)

    timezone = models.CharField(max_length=128, null=True, blank=True)
    last_cost = models.FloatField(null=True, blank=True)
    last_cost_observed = models.FloatField(null=True, blank=True)

    @classmethod
    def unique_identifier(cls):
        app_code = AppCode.objects.filter(claimed=False).order_by('?').first()

        app_code.claimed = True
        app_code.claim_date = timezone.now()
        app_code.save()

        count = AppCode.objects.filter(claimed=False).count()

        if (count % settings.APP_CODE_REMINDER_EMAIL_COUNT) == 0:
            context = {
                'count': count
            }

            subject = render_to_string('study_mail_remaining_app_codes_subject.txt', context)
            body = render_to_string('study_mail_remaining_app_codes_body.txt', context)

            message = EmailMultiAlternatives(subject, body, settings.AUTOMATED_EMAIL_FROM_ADDRESS, [settings.ADMINS[0][1]])

            message.send()

        return app_code.identifier

    def __unicode__(self):
        return self.email_address

    def emails_enabled(self):
        return self.email_enabled

    def enable_emails(self, enabled):
        self.email_enabled = enabled

        self.save()

    def user_hash(self):
        sha256 = hashlib.sha256()

        sha256.update(('%s-%s-%s' % (settings.SECRET_KEY, self.pk, self.identifier)).encode('utf-8'))

        return sha256.hexdigest()

    def fetch_timezone(self, force_recalculate=False):
        if force_recalculate is False and self.timezone is not None and self.timezone != '':
            return self.timezone

        if self.timezone is None:
            self.timezone = settings.TIME_ZONE

        source_reference = DataSourceReference.reference_for_source(self.identifier)

        latest_point = DataPoint.objects.filter(source_reference=source_reference).order_by('-created').first()

        if latest_point is not None:
            properties = latest_point.fetch_properties()

            if 'timezone' in properties['passive-data-metadata']:
                self.timezone = properties['passive-data-metadata']['timezone']

        self.save()

        return self.timezone

    def fetch_last_cost(self, force_recalculate=False):
        if force_recalculate is False and self.last_cost is not None:
            if self.last_cost < 0:
                return None

            return self.last_cost

        source_reference = DataSourceReference.reference_for_source(self.identifier)
        generator_definition = DataGeneratorDefinition.definition_for_identifier('pdk-app-event')

        last_cost = DataPoint.objects.filter(source_reference=source_reference, generator_definition=generator_definition, secondary_identifier='set-snooze-cost').order_by('-created').first()

        if last_cost is not None:
            properties = last_cost.fetch_properties()

            self.last_cost = properties['event_details']['snooze-cost']
            self.last_cost_observed = properties['observed']
        else:
            self.last_cost = -1
            self.last_cost_observed = -1

        self.save()

        if self.last_cost < 0:
            return None

        return self.last_cost

    def fetch_last_cost_observed(self, force_recalculate=False):
        if force_recalculate is False and self.last_cost_observed is not None:
            if self.last_cost_observed < 0:
                return None

            return self.last_cost_observed

        self.fetch_last_cost()

        if self.last_cost_observed < 0:
            return None

        return self.last_cost_observed

    def generate_identifier(self, use_identifier=None):
        if use_identifier is None:
            self.identifier = Participant.unique_identifier()
        else:
            self.identifier = use_identifier

        self.save()

        # call_command('update_participant_data_quality')

        baseline_phase = TreatmentPhase(participant=self)

        baseline_phase.start_date = timezone.now().date()
        baseline_phase.receives_subsidy = False
        baseline_phase.blocker_type = 'none'
        baseline_phase.snooze_delay = 5
        baseline_phase.treatment_active = False

        baseline_phase.save()

    def assign_server(self):
        app_code = AppCode.objects.filter(identifier=self.identifier).first()

        if app_code is not None:
            if app_code.configuration != '':
                config = json.loads(app_code.configuration)

                if 'server' in config:
                    server = DataServer.objects.filter(name=config['server']).first()

                    if server is not None:
                        source = DataSource.objects.filter(identifier=self.identifier).first()

                        if source is not None:
                            source.server = server
                            source.save()

    def send_welcome_email(self):
        context = {}
        context['participant'] = self

        subject = render_to_string('study_welcome_mail_subject.txt', context)
        body = render_to_string('study_welcome_mail_body.txt', context)
        body_html = render_to_string('study_welcome_mail_body.html', context)

        while '\n\n\n' in body:
            body = body.replace('\n\n\n', '\n\n')

        message = EmailMultiAlternatives(subject, body, settings.AUTOMATED_EMAIL_FROM_ADDRESS, [self.email_address])
        message.attach_alternative(body_html, "text/html")

        message.send()

    def send_relaunch_email(self):
        if self.emails_enabled() and (self.email_address.endswith('@example.com') is False):
            now = timezone.now()

            if self.last_reminder_sent is None:
                self.last_reminder_sent = now - datetime.timedelta(days=30)

            elapsed = timezone.now() - self.last_reminder_sent

            if elapsed.total_seconds() > (24 * 60 * 60):
                context = {}
                context['participant'] = self
                context['site_url'] = settings.SITE_URL

                subject = render_to_string('study_mail_launch_app_subject.txt', context)
                body = render_to_string('study_mail_launch_app_body.txt', context)

                while '\n\n\n' in body:
                    body = body.replace('\n\n\n', '\n\n')

                message = EmailMultiAlternatives(subject, body, settings.AUTOMATED_EMAIL_FROM_ADDRESS, [self.email_address])

                message.send()

                self.last_reminder_sent = now
                self.save()

                payload = {
                    'subject': subject,
                    'body': body,
                    'address': self.email_address,
                    'identifier': self.identifier,
                }

                DataPoint.objects.create_data_point('nyu-relaunch-email', 'update-participant-script', payload)

    def fetch_usage_for_date(self, date):
        metadata = json.loads(self.metadata)

        key = date.isoformat()

        daily_usage = None

        if ('daily_usages' in metadata) is False:
            metadata['daily_usages'] = {}
        elif key in metadata['daily_usages']:
            daily_usage = metadata['daily_usages'][key]

        if daily_usage is None: # pylint: disable=too-many-nested-blocks
            generator_definition = DataGeneratorDefinition.objects.filter(generator_identifier='pdk-foreground-application').first()
            source_reference = DataSourceReference.objects.filter(source=self.identifier).first()

            if (generator_definition is not None) and (source_reference is not None):
                duration = 0

                if DataPoint.objects.filter(generator_definition=generator_definition, source_reference=source_reference).count() > 0:
                    here_tz = self.fetch_timezone()

                    start = arrow.get(datetime.datetime(date.year, date.month, date.day, 0, 0, 0, 0), here_tz)
                    end = start.shift(days=1)

                    points = DataPoint.objects.filter(generator_definition=generator_definition, source_reference=source_reference, created__gte=start.datetime, created__lt=end.datetime).order_by('created')

                    last_seen = None

                    for point in points:
                        payload = point.fetch_properties()

                        if ('duration' in payload) and ('screen_active' in payload) and payload['screen_active']:
                            if last_seen is None:
                                duration += payload['duration']
                            elif (point.created - last_seen).total_seconds() * 1000 < payload['duration']:
                                duration += (point.created - last_seen).total_seconds() * 1000
                            else:
                                duration += payload['duration']


                        last_seen = point.created

                metadata['daily_usages'][key] = duration
            else:
                metadata['daily_usages'][key] = 0

            self.metadata = json.dumps(metadata, indent=2)
            self.save()

        return metadata['daily_usages'][key]

class TreatmentPhase(models.Model):
    participant = models.ForeignKey(Participant, related_name='phases', on_delete=models.CASCADE)

    start_date = models.DateField(db_index=True)

    receives_subsidy = models.BooleanField(default=True)
    blocker_type = models.CharField(choices=BLOCKER_TYPES, default='none', max_length=32)
    snooze_delay = models.IntegerField(default=0)
    treatment_active = models.BooleanField(default=False)

    calculation_start_offset = models.IntegerField(default=1)
    calculation_end_offset = models.IntegerField(default=1)

    initial_snooze_amount = models.FloatField(default=10)

    def end_date(self):
        next_treatment = TreatmentPhase.objects.filter(participant=self.participant, start_date__gt=self.start_date).order_by('start_date').first()

        if next_treatment is not None:
            return next_treatment.start_date

        return None

    def identifier(self):
        return self.participant.identifier

class AppVersion(models.Model):
    added = models.DateTimeField()

    version_name = models.CharField(max_length=32)
    version_code = models.IntegerField()
    download_url = models.URLField(max_length=512)

    release_notes = models.TextField(max_length=4096)


class AppCode(models.Model):
    identifier = models.CharField(max_length=1024, unique=True)
    claimed = models.BooleanField(default=False)
    claim_date = models.DateTimeField(null=True, blank=True)
    generate_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    configuration = models.TextField(max_length=(1024 * 1024)) # pylint: disable=superfluous-parens

    def study_server(self):
        if self.configuration != '':
            config = json.loads(self.configuration)

            if 'server' in config:
                return config['server']

        return None


class AppPackageInfo(models.Model):
    original_package = models.CharField(max_length=512)
    replacement_package = models.CharField(max_length=512, null=True, blank=True)

    sort_order = models.IntegerField(default=100)

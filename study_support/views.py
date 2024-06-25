# pylint: disable=line-too-long,no-member
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
import datetime
import json
import io
import time
import traceback

import pytz

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from passive_data_kit.models import DataPoint, DataSourceReference, DataGeneratorDefinition

from .models import Participant, TreatmentPhase, AppVersion, AppCode, AppPackageInfo

@csrf_exempt
def enroll_email(request, repeats_remaining=10):
    response = {}

    if repeats_remaining == 0:
        return HttpResponse(json.dumps(response, indent=2), content_type='application/json', status=500)

    email = request.POST.get('email', request.GET.get('email', None))

    if email is not None:
        email_address = email.strip().lower()

        participant = Participant.objects.filter(email_address=email_address).first()

        if participant is None:
            participant = Participant(email_address=email_address, created=timezone.now())

            try:
                participant.generate_identifier()

                call_command('study_seed_participants')

                # participant.assign_server()

            except IntegrityError:
                # Added delay + repeat call for cases where duplicate HTTP calls may be
                # trying to fetch the user before the steps above have finished.

                traceback.print_exc()

                time.sleep(3)

                return enroll_email(request, repeats_remaining=(repeats_remaining - 1)) # pylint: disable=superfluous-parens

        participant.send_welcome_email()

        response['identifier'] = participant.identifier

    return HttpResponse(json.dumps(response, indent=2), content_type='application/json', status=200)


@csrf_exempt
def study_configuration(request): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    response = {}

    identifier = None

    version = None

    if request.method == 'POST':
        if 'identifier' in request.POST:
            identifier = request.POST['identifier']

        if 'version' in request.POST:
            version = request.POST['version']

    elif request.method == 'GET':
        if 'identifier' in request.GET:
            identifier = request.GET['identifier']

        if 'version' in request.GET:
            version = request.GET['version']

    if identifier is not None:
        participant = Participant.objects.filter(identifier=identifier).first()

        if participant is not None:
            response['identifier'] = participant.identifier

            user_tz = participant.fetch_timezone()

            now = timezone.now().astimezone(pytz.timezone(user_tz))

            latest_phase = participant.phases.filter(start_date__lte=now.date()).order_by('-start_date').first()

            if version is not None and latest_phase is not None and latest_phase.blocker_type != 'flexible_snooze':
                latest_phase.treatment_active = False
                latest_phase.save()

                latest_phase = None

            if latest_phase is None:
                latest_phase = TreatmentPhase(participant=participant)

                latest_phase.start_date = now.date()
                latest_phase.receives_subsidy = False
                latest_phase.blocker_type = 'flexible_snooze'
                latest_phase.snooze_delay = 5
                latest_phase.treatment_active = True

                latest_phase.save()

            response['fetch_date'] = now.date().isoformat()
            response['receives_subsidy'] = latest_phase.receives_subsidy
            response['blocker_type'] = latest_phase.blocker_type
            response['snooze_delay'] = latest_phase.snooze_delay
            response['treatment_active'] = latest_phase.treatment_active
            response['start_date'] = latest_phase.start_date.isoformat()
            response['calculation_start'] = (latest_phase.start_date + datetime.timedelta(days=latest_phase.calculation_start_offset)).isoformat()
            response['initial_snooze_amount'] = latest_phase.initial_snooze_amount

            next_phase = participant.phases.filter(start_date__gt=latest_phase.start_date).order_by('start_date').first()

            if next_phase is not None:
                response['end_date'] = next_phase.start_date.isoformat()
                response['calculation_end'] = (next_phase.start_date - datetime.timedelta(days=latest_phase.calculation_end_offset)).isoformat()

            prior_phase = participant.phases.filter(start_date__lt=latest_phase.start_date).order_by('-start_date').first()

            if prior_phase is not None:
                response['prior_start_date'] = prior_phase.start_date.isoformat()

            snoozes = []

            source_reference = DataSourceReference.reference_for_source(participant.identifier)
            generator_definition = DataGeneratorDefinition.definition_for_identifier('app-snooze')

            for snooze in DataPoint.objects.filter(source_reference=source_reference, generator_definition=generator_definition):
                properties = snooze.fetch_properties()

                existing_snooze = {
                    'duration': properties['duration'],
                    'observed': properties['observed'],
                    'app_package': properties['app_package']
                }

                snoozes.append(existing_snooze)

            response['snoozes'] = snoozes

            last_cost = participant.fetch_last_cost()
            last_cost_observed = participant.fetch_last_cost_observed()

            if last_cost is not None and last_cost_observed is not None:
                response['snooze_cost'] = last_cost
                response['snooze_cost_set'] = last_cost_observed

            app_infos = []

            for package in AppPackageInfo.objects.all().order_by('sort_order', 'original_package'):
                app_info = {
                    'original_package': package.original_package,
                    'sort_order': package.sort_order,
                }

                if package.replacement_package is not None:
                    app_info['replacement_package'] = package.replacement_package

                app_infos.append(app_info)

            response['apps'] = app_infos

    http_resp = HttpResponse(json.dumps(response, indent=2), content_type='application/json', status=200)

    http_resp['Access-Control-Allow-Origin'] = '*'
    http_resp['Access-Control-Allow-Methods'] = 'POST'
    http_resp['Access-Control-Request-Headers'] = 'Content-Type'
    http_resp['Access-Control-Allow-Headers'] = 'Content-Type'

    return http_resp

@staff_member_required
def treatment_phases(request):
    context = {}

    context['messages'] = []

    if request.method == 'POST': # pylint: disable=too-many-nested-blocks
        if 'file_upload' in request.FILES:

            data = csv.reader(request.FILES['file_upload'], delimiter=str('\t'))

            for row in data:
                if row[0] == 'AppCode':
                    pass # Header row
                else:
                    try:
                        app_code = row[0]
                        receives_subsidy = (row[1] == '1') # pylint: disable=superfluous-parens
                        blocker_type = row[2]
                        snooze_delay = int(float(row[3]))

                        date_components = row[4].split('-')

                        start_date = datetime.date(int(date_components[0]), int(date_components[1]), int(date_components[2]))

                        treatment_active = (row[6] == '1') # pylint: disable=superfluous-parens

                        participant = Participant.objects.filter(identifier=app_code).first()

                        if participant is None:
                            context['messages'].append(['error', 'No user with app code "' + app_code + '" found.'])
                        else:
                            existing_treatment = TreatmentPhase.objects.filter(participant=participant, start_date=start_date).first()

                            if existing_treatment is not None:
                                updated = TreatmentPhase.objects.filter(participant=participant, start_date=start_date).update(receives_subsidy=receives_subsidy, blocker_type=blocker_type, snooze_delay=snooze_delay, treatment_active=treatment_active)

                                context['messages'].append(['info', 'Updated ' + str(updated) + ' treatment phase(s) matching app code "' + app_code + '" and start date "' + str(start_date) + '".'])
                            else:
                                phase = TreatmentPhase(participant=participant, start_date=start_date, receives_subsidy=receives_subsidy, blocker_type=blocker_type, snooze_delay=snooze_delay, treatment_active=treatment_active)
                                phase.save()

                                context['messages'].append(['info', 'Created new treatment phase for app code "' + app_code + '" on start date "' + str(start_date) + '".'])
                    except: # pylint: disable=bare-except
                        traceback.print_exc()
                        context['messages'].append(['error', 'Unable to properly parse values ' + str(row) + '.\n\nVerify that the uploaded file follows the same format as the downloaded file.'])

        else:
            context['error'] = 'No readable file was uploaded.'

    start_date = datetime.datetime(2020, 1, 1, 0, 0, 0, 0, tzinfo=pytz.timezone(settings.TIME_ZONE))

    context['phases'] = TreatmentPhase.objects.order_by('-start_date')

    return render(request, 'study_treatment_phases.html', context=context)

@staff_member_required
def treatment_phases_txt(request): # pylint: disable=unused-argument
    phases = TreatmentPhase.objects.all().order_by('start_date')

    string_buffer = io.StringIO()

    writer = csv.writer(string_buffer, delimiter=str('\t'))

    headers = [
        'AppCode',
        'ReceivesSubsidy',
        'BlockerType',
        'SnoozeDelay',
        'StartDate',
        'EndDate',
        'TreatmentActive'
    ]

    writer.writerow(headers)

    for phase in phases:
        row = []

        row.append(phase.participant.identifier)

        if phase.receives_subsidy:
            row.append(1)
        else:
            row.append(0)

        row.append(phase.blocker_type)
        row.append(phase.snooze_delay)
        row.append(phase.start_date.isoformat())

        end_date = phase.end_date()

        if end_date is not None:
            row.append(end_date.isoformat())
        else:
            row.append('')

        if phase.treatment_active:
            row.append(1)
        else:
            row.append(0)

        writer.writerow(row)

    http_resp = HttpResponse(string_buffer.getvalue(), content_type='text/plain', status=200)
    http_resp['Content-Disposition'] = 'attachment; filename="treatment-phases.txt"'

    return http_resp

@staff_member_required
def app_codes_txt(request): # pylint: disable=unused-argument
    app_codes = AppCode.objects.all().order_by('claimed', 'claim_date')

    string_buffer = io.StringIO()

    writer = csv.writer(string_buffer, delimiter=str('\t'))

    headers = [
        'App Code',
        'Claimed',
        'Claimed Date',
        'Server',
    ]

    writer.writerow(headers)

    for app_code in app_codes:
        row = []

        row.append(app_code.identifier)

        if app_code.claimed:
            row.append(1)
        else:
            row.append(0)

        if app_code.claim_date is not None:
            row.append(app_code.claim_date.isoformat())
        else:
            row.append('')


        if app_code.configuration != '':
            config = json.loads(app_code.configuration)

            if 'server' in config:
                row.append(config['server'])
            else:
                row.append('')

        writer.writerow(row)

    http_resp = HttpResponse(string_buffer.getvalue(), content_type='text/plain', status=200)
    http_resp['Content-Disposition'] = 'attachment; filename="app-codes.txt"'

    return http_resp


def activate_treatments(request, app_code):
    context = {}

    context['app_code'] = app_code

    participant = get_object_or_404(Participant, identifier=app_code)

    TreatmentPhase.objects.filter(participant=participant).update(treatment_active=True)

    return render(request, 'study_activate_treatments.html', context=context)


def deactivate_treatments(request, app_code):
    context = {}

    context['app_code'] = app_code

    participant = get_object_or_404(Participant, identifier=app_code)

    TreatmentPhase.objects.filter(participant=participant).update(treatment_active=False)

    return render(request, 'study_deactivate_treatments.html', context=context)


def activate_treatments_json(request, app_code): # pylint: disable=unused-argument
    response = {
        'success': False
    }

    participant = Participant.objects.filter(identifier=app_code).first()

    if participant is not None:
        TreatmentPhase.objects.filter(participant=participant).update(treatment_active=True)
        response['success'] = True

    http_resp = HttpResponse(json.dumps(response, indent=2), content_type='application/json', status=200)

    http_resp['Access-Control-Allow-Origin'] = '*'
    http_resp['Access-Control-Allow-Methods'] = 'POST'
    http_resp['Access-Control-Request-Headers'] = 'Content-Type'
    http_resp['Access-Control-Allow-Headers'] = 'Content-Type'

    return http_resp


def deactivate_treatments_json(request, app_code): # pylint: disable=unused-argument
    response = {
        'success': False
    }

    participant = Participant.objects.filter(identifier=app_code).first()

    if participant is not None:
        TreatmentPhase.objects.filter(participant=participant).update(treatment_active=False)
        response['success'] = True

    http_resp = HttpResponse(json.dumps(response, indent=2), content_type='application/json', status=200)

    http_resp['Access-Control-Allow-Origin'] = '*'
    http_resp['Access-Control-Allow-Methods'] = 'POST'
    http_resp['Access-Control-Request-Headers'] = 'Content-Type'
    http_resp['Access-Control-Allow-Headers'] = 'Content-Type'

    return http_resp

def latest_version(request): # pylint: disable=unused-argument
    response = {}

    latest = AppVersion.objects.order_by('-added').first()

    if latest is not None:
        response['latestVersion'] = latest.version_name
        response['latestVersionCode'] = latest.version_code
        response['url'] = latest.download_url

    return HttpResponse(json.dumps(response, indent=2), content_type='application/json', status=200)


def email_opt_out(request, user_hash):
    context = {}

    if request.method == 'POST':
        for participant in Participant.objects.all():
            if user_hash == participant.user_hash():
                now = timezone.now()

                participant.last_reminder_sent = now + datetime.timedelta(days=(365 * 100)) # pylint: disable=superfluous-parens
                participant.enable_emails(False)
                participant.save()

                context['cancelled'] = True
                context['user_hash'] = user_hash
    else:
        context['user_hash'] = user_hash

    return render(request, 'study_email_opt_out.html', context=context)

@csrf_exempt
def fetch_participant_data_quality(request):
    metadata = {}

    if 'identifier' in request.POST and 'request-key' in request.POST:
        try:
            if request.POST['request-key'] == settings.PDK_REQUEST_KEY:
                participant = Participant.objects.filter(identifier=request.POST['identifier']).first()

                if participant is not None:
                    metadata = json.loads(participant.metadata)
        except AttributeError:
            pass

    return JsonResponse(metadata, safe=False, json_dumps_params={'indent': 2})

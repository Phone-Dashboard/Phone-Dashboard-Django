# pylint: disable=line-too-long
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.gis import admin

from .models import Participant, TreatmentPhase, AppVersion, AppCode, AppPackageInfo

@admin.register(Participant)
class ParticipantAdmin(admin.OSMGeoAdmin):
    list_display = ('email_address', 'identifier', 'created', 'timezone', 'performance_last_updated', 'user_hash',)
    search_fields = ['email_address', 'identifier', 'metadata',]

    list_filter = ('created', 'performance_last_updated', 'timezone', 'email_enabled')

@admin.register(TreatmentPhase)
class TreatmentPhaseAdmin(admin.OSMGeoAdmin):
    list_display = ('participant', 'identifier', 'start_date', 'receives_subsidy', 'blocker_type', 'snooze_delay', 'treatment_active',)

    search_fields = ['participant__email_address', 'participant__identifier',]

    list_filter = ('treatment_active', 'start_date', 'receives_subsidy', 'blocker_type', 'snooze_delay',)

@admin.register(AppVersion)
class AppVersionAdmin(admin.OSMGeoAdmin):
    list_display = ('version_name', 'version_code', 'added', 'download_url',)

    search_fields = ['release_notes', 'version_name']

    list_filter = ('added',)

@admin.register(AppCode)
class AppCodeAdmin(admin.OSMGeoAdmin):
    list_display = ('identifier', 'claimed', 'claim_date', 'generate_date', 'study_server',)

    search_fields = ['identifier', 'configuration']

    list_filter = ('claimed', 'claim_date', 'generate_date',)

@admin.register(AppPackageInfo)
class AppPackageInfoAdmin(admin.OSMGeoAdmin):
    list_display = ('original_package', 'replacement_package', 'sort_order',)

    search_fields = ['original_package', 'replacement_package']

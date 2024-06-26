# pylint: disable=line-too-long

from django.urls import re_path

from .views import enroll_email, study_configuration, treatment_phases, treatment_phases_txt, \
                   activate_treatments, deactivate_treatments, activate_treatments_json, \
                   deactivate_treatments_json, latest_version, email_opt_out, app_codes_txt, \
                   fetch_participant_data_quality

urlpatterns = [
    re_path(r'^latest-version.json', latest_version, name='latest_version'),
    re_path(r'^enroll-email.json', enroll_email, name='enroll_email'),
    re_path(r'^data-quality.json', fetch_participant_data_quality, name='fetch_participant_data_quality'),
    re_path(r'^config.json', study_configuration, name='study_configuration'),
    re_path(r'^treatment-phases.txt$', treatment_phases_txt, name='treatment_phases_txt'),
    re_path(r'^app-codes.txt$', app_codes_txt, name='app_codes_txt'),
    re_path(r'^treatment-phases$', treatment_phases, name='treatment_phases'),
    re_path(r'^activate/(?P<app_code>.+).json$', activate_treatments_json, name='activate_treatments_json'),
    re_path(r'^deactivate/(?P<app_code>.+).json$', deactivate_treatments_json, name='deactivate_treatments_json'),
    re_path(r'^activate/(?P<app_code>.+)$', activate_treatments, name='activate_treatments'),
    re_path(r'^deactivate/(?P<app_code>.+)$', deactivate_treatments, name='deactivate_treatments'),
    re_path(r'^opt-out/(?P<user_hash>.+)$', email_opt_out, name='email_opt_out'),
]

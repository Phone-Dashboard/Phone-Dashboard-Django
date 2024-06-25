# pylint: disable=line-too-long

from django.conf.urls import url

from .views import enroll_email, study_configuration, treatment_phases, treatment_phases_txt, \
                   activate_treatments, deactivate_treatments, activate_treatments_json, \
                   deactivate_treatments_json, latest_version, email_opt_out, app_codes_txt, \
                   fetch_participant_data_quality

urlpatterns = [
    url(r'^latest-version.json', latest_version, name='latest_version'),
    url(r'^enroll-email.json', enroll_email, name='enroll_email'),
    url(r'^data-quality.json', fetch_participant_data_quality, name='fetch_participant_data_quality'),
    url(r'^config.json', study_configuration, name='study_configuration'),
    url(r'^treatment-phases.txt$', treatment_phases_txt, name='treatment_phases_txt'),
    url(r'^app-codes.txt$', app_codes_txt, name='app_codes_txt'),
    url(r'^treatment-phases$', treatment_phases, name='treatment_phases'),
    url(r'^activate/(?P<app_code>.+).json$', activate_treatments_json, name='activate_treatments_json'),
    url(r'^deactivate/(?P<app_code>.+).json$', deactivate_treatments_json, name='deactivate_treatments_json'),
    url(r'^activate/(?P<app_code>.+)$', activate_treatments, name='activate_treatments'),
    url(r'^deactivate/(?P<app_code>.+)$', deactivate_treatments, name='deactivate_treatments'),
    url(r'^opt-out/(?P<user_hash>.+)$', email_opt_out, name='email_opt_out'),
]

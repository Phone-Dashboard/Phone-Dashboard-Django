# pylint: disable=line-too-long

from django.urls import re_path

from .views import website_home, website_privacy, website_enroll

urlpatterns = [
    re_path(r'^$', website_home, name='website_home'),
    re_path(r'^privacy$', website_privacy, name='website_privacy'),
    re_path(r'^enroll$', website_enroll, name='website_enroll'),
]

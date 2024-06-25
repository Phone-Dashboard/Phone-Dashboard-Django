# pylint: disable=line-too-long

from django.conf.urls import url

from .views import website_home, website_privacy, website_enroll

urlpatterns = [
    url(r'^$', website_home, name='website_home'),
    url(r'^privacy$', website_privacy, name='website_privacy'),
    url(r'^enroll$', website_enroll, name='website_enroll'),
]

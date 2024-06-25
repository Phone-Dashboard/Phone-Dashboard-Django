# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render

def website_home(request):
    context = {}

    return render(request, 'website_home.html', context=context)


def website_privacy(request):
    context = {}

    return render(request, 'website_privacy.html', context=context)

def website_enroll(request):
    context = {}

    return render(request, 'website_enroll.html', context=context)

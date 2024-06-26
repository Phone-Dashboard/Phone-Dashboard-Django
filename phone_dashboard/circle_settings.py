import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 'CHANGEME' # nosec

DEBUG = True

ALLOWED_HOSTS = [
    '*'
]

ADMINS = [
    ('Chris Karr', 'chris@audacious-software.com')
]

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME':     'circle_test',
        'USER':     'root',
        'PASSWORD': '',
        'HOST': 'localhost',
    }
}
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR + '/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR + '/media/'

PDK_DASHBOARD_ENABLED = True

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

PDK_DASHBOARD_ENABLED = True
PDK_EXCESSIVE_VISUALIZATION_TIME = 60

PDK_TARGET_SIZE = 500000

PDK_ENABLED_CHECKS = (
    'pdk-device-battery',
)

PDK_EXTRA_GENERATORS = (
    ('nyu-full-export', 'NYU Pilot Aggregated Phone Usage',),
)

PDK_BUNDLE_PROCESS_LIMIT = 10000
PDK_REQUEST_KEY = 'CHANGEME'

AUTOMATED_EMAIL_FROM_ADDRESS = 'noreply@nyu.edu'

SITE_URL = 'https://nyu.audacious-software.com'

APP_CODE_REMINDER_EMAIL_COUNT = 25

PD_HOST_REPORT_PREFIX = 'nyu-x'

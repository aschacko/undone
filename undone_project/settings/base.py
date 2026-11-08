"""
Shared Django settings for undone_project.

Never point DJANGO_SETTINGS_MODULE at this module directly. Choose a mode:

    undone_project.settings.development   (manage.py default)
    undone_project.settings.production    (wsgi.py / asgi.py default)

Secrets and host names are read from the environment, normally via the
repository-level .env file. See .env.example for the expected variables.
"""

import os
import warnings
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# This file is <repo>/undone_project/settings/base.py, so the repository root
# is three levels up (settings/ -> undone_project/ -> <repo>).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load <repo>/.env if present. Variables already set in the real environment
# take precedence over values in the file (python-dotenv default).
load_dotenv(BASE_DIR / '.env')


def require_env(name):
    """Return environment variable `name`, or fail with setup instructions."""
    value = os.getenv(name, '').strip()
    if not value:
        raise ImproperlyConfigured(
            f"{name} is not set. Copy .env.example to .env in the project root "
            f"and give {name} a value (see README.md, 'Environment variables')."
        )
    return value


SECRET_KEY = require_env('SECRET_KEY')

# DEBUG is set in development.py (True) and production.py (False), never here.

# Comma-separated in the environment, e.g. "localhost,127.0.0.1".
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', '').split(',')
    if host.strip()
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'feedback',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Serves static files when DEBUG is off. Must sit right after
    # SecurityMiddleware; without it production 404s on the stylesheet.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'undone_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'undone_project.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# URL names, not paths, so a moved route fails loudly instead of 404ing.
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'feedback:dataset_list'
LOGOUT_REDIRECT_URL = 'feedback:home'


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
# collectstatic output; generated, so git-ignored.
STATIC_ROOT = BASE_DIR / 'staticfiles'
# WhiteNoise warns on every request until collectstatic has created
# STATIC_ROOT. That is expected in development and tests, where Django serves
# static files itself.
warnings.filterwarnings('ignore', message='No directory at: ', category=UserWarning)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# CSV upload limits (feedback/forms.py). The file is parsed in memory and only
# the rows are stored, so these bound both request size and database growth.
UPLOAD_MAX_BYTES = 5 * 1024 * 1024
UPLOAD_MAX_ROWS = 5000
# Django's own cap on in-memory request bodies; keep it above the CSV limit.
DATA_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = UPLOAD_MAX_BYTES + 1024 * 1024

"""
Production settings: DEBUG off, host list and secret key validated.

To try it locally:
    python manage.py collectstatic --settings=undone_project.settings.production
    python manage.py runserver --settings=undone_project.settings.production
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS is empty. Set it in .env to a comma-separated list of "
        "host names this site is served from (see .env.example)."
    )

if SECRET_KEY.startswith('django-insecure-') or SECRET_KEY == 'replace-with-a-new-random-key':  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY is a development/placeholder value. Generate a new one: "
        "python -c \"from django.core.management.utils import "
        "get_random_secret_key as g; print(g())\""
    )

# Hashed, compressed static files for cache busting. Run collectstatic with
# --settings=undone_project.settings.production, or no hashed files are written.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

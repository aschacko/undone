"""Development settings: DEBUG on, local hosts allowed by default."""

from .base import *  # noqa: F401,F403

DEBUG = True

if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

"""
Create a demo user and import the synthetic sample CSV, so a fresh clone has
something to look at.

    python manage.py load_demo --username demo

The password is read from the DEMO_PASSWORD environment variable or prompted
for; it is never hard-coded.
"""

import getpass
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from feedback.forms import guess_mapping
from feedback.models import Dataset
from feedback.services import decode_upload, import_rows, parse_csv

SAMPLE_CSV = Path(settings.BASE_DIR) / 'sample_data' / 'sample_cancellations.csv'
DATASET_NAME = 'Sample: H1 2026 cancellations (synthetic)'


class Command(BaseCommand):
    help = 'Create a demo user and import sample_data/sample_cancellations.csv for them.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo')

    def handle(self, *args, username, **options):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            password = os.getenv('DEMO_PASSWORD') or getpass.getpass(f'Password for new user "{username}": ')
            if not password:
                raise CommandError('A password is required (set DEMO_PASSWORD or type one).')
            user = User.objects.create_user(username=username, password=password)
            self.stdout.write(f'Created user "{username}".')

        if Dataset.objects.filter(owner=user, name=DATASET_NAME).exists():
            self.stdout.write(f'"{DATASET_NAME}" already exists for {username}; nothing to do.')
            return

        text = decode_upload(SAMPLE_CSV.read_bytes())
        headers, rows = parse_csv(text)
        dataset = Dataset.objects.create(
            owner=user, name=DATASET_NAME, source_filename=SAMPLE_CSV.name,
            description='Made-up responses for demonstrating the app; not real customer data.',
        )
        result = import_rows(dataset, headers, rows, guess_mapping(headers))
        self.stdout.write(self.style.SUCCESS(
            f'Imported {result.created} responses into "{DATASET_NAME}" '
            f'({result.skipped_empty} empty skipped, {len(result.unreadable_dates)} unreadable dates).'
        ))

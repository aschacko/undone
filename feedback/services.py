"""
CSV parsing, row import, and the hand-off point for AI theme detection.

Kept out of views.py so the upload view, the load_demo command, and the AI
pipeline all share one implementation, and so each step can be tested without
going through HTTP.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime

from django.conf import settings
from django.db import transaction

from .models import Dataset, FeedbackResponse, Theme

DATE_FORMATS = ('%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%m/%d/%y')

# Longest value kept for the short CSV fields; longer values are truncated.
SHORT_FIELD_MAX = 80


class CSVError(ValueError):
    """The uploaded file cannot be used; the message is shown to the user."""


def decode_upload(raw_bytes):
    """Decode uploaded bytes as UTF-8 (with or without a byte-order mark)."""
    try:
        return raw_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise CSVError(
            'The file is not UTF-8 text. In Excel, use "Save As → CSV UTF-8" and upload again.'
        )


def parse_csv(text):
    """Return (headers, rows) where rows is a list of lists of strings.

    Raises CSVError for anything the user needs to fix: no header, blank or
    duplicate column names, no data rows, or more rows than UPLOAD_MAX_ROWS.
    """
    try:
        reader = csv.reader(io.StringIO(text))
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        raise CSVError(f'The file could not be read as CSV ({exc}).')

    if not all_rows:
        raise CSVError('The file is empty.')

    headers = [h.strip() for h in all_rows[0]]
    if any(not h for h in headers):
        raise CSVError('Every column needs a name in the first (header) row.')
    if len(set(headers)) != len(headers):
        raise CSVError('Two or more columns have the same name. Rename them and upload again.')

    rows = all_rows[1:]
    if not rows:
        raise CSVError('The file has a header row but no data rows.')
    if len(rows) > settings.UPLOAD_MAX_ROWS:
        raise CSVError(
            f'The file has {len(rows):,} rows; the limit is {settings.UPLOAD_MAX_ROWS:,}.'
        )
    return headers, rows


def parse_date(value):
    """Parse a date in one of DATE_FORMATS; return None if blank or unrecognised."""
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class ImportResult:
    created: int = 0
    skipped_empty: int = 0
    unreadable_dates: list = field(default_factory=list)  # CSV row numbers


@transaction.atomic
def import_rows(dataset, headers, rows, mapping):
    """Create one FeedbackResponse per row and mark the dataset READY.

    `mapping` maps our field names ('text', 'date', 'plan', 'segment') to CSV
    header names; only 'text' is required. Rows with blank feedback text are
    skipped. Runs in one transaction, so a failure leaves no partial import.
    """
    index = {name: headers.index(col) for name, col in mapping.items() if col}

    def cell(row, name):
        i = index.get(name)
        return row[i].strip() if i is not None and i < len(row) else ''

    result = ImportResult()
    objects = []
    for row_number, row in enumerate(rows, start=1):
        text = cell(row, 'text')
        if not text:
            result.skipped_empty += 1
            continue
        raw_date = cell(row, 'date')
        cancelled_on = parse_date(raw_date)
        if raw_date and cancelled_on is None:
            result.unreadable_dates.append(row_number)
        objects.append(FeedbackResponse(
            dataset=dataset,
            row_number=row_number,
            text=text,
            cancelled_on=cancelled_on,
            plan=cell(row, 'plan')[:SHORT_FIELD_MAX],
            segment=cell(row, 'segment')[:SHORT_FIELD_MAX],
        ))

    if not objects:
        raise CSVError('Every row has an empty feedback column, so there is nothing to analyze.')

    FeedbackResponse.objects.bulk_create(objects)
    result.created = len(objects)
    dataset.status = Dataset.Status.READY
    dataset.raw_csv = ''
    dataset.save(update_fields=['status', 'raw_csv', 'updated_at'])
    return result


# ---------------------------------------------------------------------------
# AI hand-off (Part 3). The model code lives elsewhere; these two functions are
# the only contract between it and the database.
# ---------------------------------------------------------------------------

def responses_for_analysis(dataset):
    """Return [(response_id, text), ...] for every response in the dataset."""
    return list(dataset.responses.values_list('id', 'text'))


@transaction.atomic
def apply_theme_assignments(dataset, assignments):
    """Save AI theme assignments for a dataset.

    `assignments` maps response_id -> (theme_name, confidence or None). Theme
    names are created as AI themes if they do not already exist in this
    dataset. Ids that are not in this dataset are ignored, so a model can never
    write into another user's data. Returns the number of responses updated.
    """
    valid_ids = set(dataset.responses.values_list('id', flat=True))
    themes = {t.name: t for t in dataset.themes.all()}
    updated = 0
    for response_id, (theme_name, confidence) in assignments.items():
        if response_id not in valid_ids:
            continue
        theme_name = (theme_name or '').strip()[:SHORT_FIELD_MAX]
        if not theme_name:
            continue
        theme = themes.get(theme_name)
        if theme is None:
            theme = Theme.objects.create(dataset=dataset, name=theme_name, source=Theme.Source.AI)
            themes[theme_name] = theme
        updated += FeedbackResponse.objects.filter(pk=response_id).update(
            theme=theme, theme_confidence=confidence
        )
    dataset.status = Dataset.Status.ANALYZED
    dataset.save(update_fields=['status', 'updated_at'])
    return updated

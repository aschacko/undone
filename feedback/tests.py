import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import guess_mapping
from .models import Dataset, FeedbackResponse, Theme
from .services import (
    CSVError, apply_theme_assignments, import_rows, parse_csv, parse_date, responses_for_analysis,
)

User = get_user_model()

SAMPLE = (
    'id,cancel_date,plan,reason\n'
    '1,2026-01-05,Basic,Too expensive\n'
    '2,2026-01-20,Pro,Missing SSO\n'
    '3,02/03/2026,Basic,App crashes on export\n'
    '4,not a date,Pro,Price went up\n'
    '5,2026-02-10,Basic,\n'
)
MAPPING = {'text': 'reason', 'date': 'cancel_date', 'plan': 'plan', 'segment': ''}


def csv_file(content=SAMPLE, name='feedback.csv'):
    return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/csv')


def make_dataset(owner, name='Q1', content=SAMPLE):
    dataset = Dataset.objects.create(owner=owner, name=name, source_filename='feedback.csv')
    headers, rows = parse_csv(content)
    import_rows(dataset, headers, rows, MAPPING)
    return dataset


class ParsingTests(TestCase):
    def test_parse_csv_returns_headers_and_skips_blank_lines(self):
        headers, rows = parse_csv('a,b\n1,2\n\n3,4\n')
        self.assertEqual(headers, ['a', 'b'])
        self.assertEqual(rows, [['1', '2'], ['3', '4']])

    def test_rejects_empty_header_only_duplicate_and_unnamed(self):
        for text in ('', 'a,b\n', 'a,a\n1,2\n', 'a,\n1,2\n'):
            with self.subTest(text=text), self.assertRaises(CSVError):
                parse_csv(text)

    @override_settings(UPLOAD_MAX_ROWS=2)
    def test_rejects_too_many_rows(self):
        with self.assertRaises(CSVError):
            parse_csv('a\n1\n2\n3\n')

    def test_parse_date_formats(self):
        self.assertEqual(parse_date('2026-03-04'), date(2026, 3, 4))
        self.assertEqual(parse_date('03/04/2026'), date(2026, 3, 4))
        self.assertIsNone(parse_date('sometime in June'))
        self.assertIsNone(parse_date(''))

    def test_guess_mapping_uses_each_column_once(self):
        guess = guess_mapping(['customer_id', 'cancel_date', 'plan', 'region', 'cancellation_reason'])
        self.assertEqual(guess, {
            'text': 'cancellation_reason', 'date': 'cancel_date', 'plan': 'plan', 'segment': 'region',
        })


class ImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='pw-123456789')

    def test_import_skips_empty_text_and_reports_bad_dates(self):
        dataset = Dataset.objects.create(owner=self.user, name='Q1', source_filename='f.csv', raw_csv=SAMPLE)
        headers, rows = parse_csv(SAMPLE)
        result = import_rows(dataset, headers, rows, MAPPING)

        self.assertEqual(result.created, 4)
        self.assertEqual(result.skipped_empty, 1)
        self.assertEqual(result.unreadable_dates, [4])
        dataset.refresh_from_db()
        self.assertEqual(dataset.status, Dataset.Status.READY)
        self.assertEqual(dataset.raw_csv, '', 'raw CSV should be cleared after import')
        third = dataset.responses.get(row_number=3)
        self.assertEqual((third.plan, third.cancelled_on), ('Basic', date(2026, 2, 3)))

    def test_all_empty_rows_imports_nothing(self):
        dataset = Dataset.objects.create(owner=self.user, name='Q1', source_filename='f.csv')
        headers, rows = parse_csv('reason,plan\n,Basic\n,Pro\n')
        with self.assertRaises(CSVError):
            import_rows(dataset, headers, rows, {'text': 'reason'})
        self.assertEqual(FeedbackResponse.objects.count(), 0)
        dataset.refresh_from_db()
        self.assertEqual(dataset.status, Dataset.Status.MAPPING)


class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='pw-123456789')
        self.dataset = make_dataset(self.user)

    def test_theme_from_other_dataset_is_invalid(self):
        other = make_dataset(self.user, name='Q2')
        foreign_theme = Theme.objects.create(dataset=other, name='Pricing')
        response = self.dataset.responses.first()
        response.theme = foreign_theme
        with self.assertRaises(ValidationError):
            response.full_clean()

    def test_deleting_theme_unassigns_but_keeps_responses(self):
        theme = Theme.objects.create(dataset=self.dataset, name='Pricing')
        self.dataset.responses.update(theme=theme)
        theme.delete()
        self.assertEqual(self.dataset.responses.count(), 4)
        self.assertFalse(self.dataset.responses.filter(theme__isnull=False).exists())

    def test_deleting_dataset_cascades(self):
        Theme.objects.create(dataset=self.dataset, name='Pricing')
        self.dataset.delete()
        self.assertEqual(FeedbackResponse.objects.count(), 0)
        self.assertEqual(Theme.objects.count(), 0)


class AIHandOffTests(TestCase):
    """The contract the AI step (Part 3) will use to write results."""

    def setUp(self):
        self.user = User.objects.create_user('ana', password='pw-123456789')
        self.dataset = make_dataset(self.user)

    def test_responses_for_analysis_lists_id_and_text(self):
        pairs = responses_for_analysis(self.dataset)
        self.assertEqual(len(pairs), 4)
        self.assertIn('Too expensive', [text for _, text in pairs])

    def test_apply_assignments_creates_ai_themes_and_ignores_foreign_ids(self):
        other_user = User.objects.create_user('ben', password='pw-123456789')
        foreign = make_dataset(other_user).responses.first()
        ids = list(self.dataset.responses.values_list('id', flat=True))
        updated = apply_theme_assignments(self.dataset, {
            ids[0]: ('Pricing', 0.91),
            ids[3]: ('Pricing', 0.88),
            ids[1]: ('Missing features', 0.75),
            foreign.id: ('Pricing', 0.99),
        })
        self.assertEqual(updated, 3)
        self.assertEqual(set(self.dataset.themes.values_list('name', 'source')),
                         {('Pricing', 'ai'), ('Missing features', 'ai')})
        foreign.refresh_from_db()
        self.assertIsNone(foreign.theme, "another user's response must never be touched")
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.status, Dataset.Status.ANALYZED)


class AuthTests(TestCase):
    def test_protected_pages_redirect_to_login(self):
        user = User.objects.create_user('ana', password='pw-123456789')
        dataset = make_dataset(user)
        for url in (
            reverse('feedback:dataset_list'),
            reverse('feedback:upload'),
            reverse('feedback:dataset_detail', args=[dataset.pk]),
            reverse('feedback:response_list', args=[dataset.pk]),
            reverse('feedback:export_csv', args=[dataset.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_signup_logs_in_and_goes_to_upload(self):
        response = self.client.post(reverse('feedback:signup'), {
            'username': 'newbie', 'email': '', 'password1': 'a-Long-pass-9876', 'password2': 'a-Long-pass-9876',
        })
        self.assertRedirects(response, reverse('feedback:upload'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newbie').pk)

    def test_public_pages_render(self):
        for name in ('feedback:home', 'login', 'feedback:signup'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


class OwnershipTests(TestCase):
    """A signed-in user must not be able to read or change another user's data."""

    def setUp(self):
        self.owner = User.objects.create_user('ana', password='pw-123456789')
        self.intruder = User.objects.create_user('eve', password='pw-123456789')
        self.dataset = make_dataset(self.owner)
        self.theme = Theme.objects.create(dataset=self.dataset, name='Pricing')
        self.client.force_login(self.intruder)

    def test_every_dataset_url_is_404_for_other_users(self):
        pk = self.dataset.pk
        response_pk = self.dataset.responses.first().pk
        gets = [
            reverse('feedback:dataset_detail', args=[pk]),
            reverse('feedback:map_columns', args=[pk]),
            reverse('feedback:dataset_edit', args=[pk]),
            reverse('feedback:dataset_delete', args=[pk]),
            reverse('feedback:response_list', args=[pk]),
            reverse('feedback:theme_create', args=[pk]),
            reverse('feedback:theme_edit', args=[pk, self.theme.pk]),
            reverse('feedback:theme_delete', args=[pk, self.theme.pk]),
            reverse('feedback:export_csv', args=[pk]),
            reverse('feedback:api_dataset_summary', args=[pk]),
        ]
        for url in gets:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        posts = [
            reverse('feedback:dataset_delete', args=[pk]),
            reverse('feedback:theme_delete', args=[pk, self.theme.pk]),
            reverse('feedback:assign_theme', args=[pk, response_pk]),
        ]
        for url in posts:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {'theme': self.theme.pk}).status_code, 404)
        self.assertTrue(Dataset.objects.filter(pk=pk).exists())
        self.assertTrue(Theme.objects.filter(pk=self.theme.pk).exists())

    def test_dataset_list_shows_only_own_datasets(self):
        response = self.client.get(reverse('feedback:dataset_list'))
        self.assertNotContains(response, self.dataset.name)


class UploadWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='pw-123456789')
        self.client.force_login(self.user)

    def test_full_upload_then_map_then_dashboard(self):
        response = self.client.post(reverse('feedback:upload'), {
            'name': 'Q1 cancellations', 'description': '', 'file': csv_file(),
        })
        dataset = Dataset.objects.get(name='Q1 cancellations')
        self.assertRedirects(response, reverse('feedback:map_columns', args=[dataset.pk]))
        self.assertEqual(dataset.status, Dataset.Status.MAPPING)

        page = self.client.get(reverse('feedback:map_columns', args=[dataset.pk]))
        self.assertContains(page, 'Too expensive')  # preview
        self.assertEqual(page.context['form'].initial['text'], 'reason')

        response = self.client.post(reverse('feedback:map_columns', args=[dataset.pk]), {
            'text': 'reason', 'date': 'cancel_date', 'plan': 'plan', 'segment': '',
        }, follow=True)
        self.assertRedirects(response, reverse('feedback:dataset_detail', args=[dataset.pk]))
        self.assertContains(response, 'Imported 4 responses')
        self.assertContains(response, 'Skipped 1 rows with empty feedback')
        self.assertContains(response, '1 dates could not be read')
        self.assertEqual(dataset.responses.count(), 4)

    def test_upload_rejects_non_csv_and_duplicate_name(self):
        make_dataset(self.user, name='Taken')
        response = self.client.post(reverse('feedback:upload'), {
            'name': 'taken', 'file': csv_file(name='notes.txt'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'name', 'You already have a dataset with this name.')
        self.assertFormError(response.context['form'], 'file', 'Please upload a .csv file.')

    def test_upload_rejects_non_utf8(self):
        bad = SimpleUploadedFile('f.csv', 'reason\nprix élevé\n'.encode('latin-1'))
        response = self.client.post(reverse('feedback:upload'), {'name': 'X', 'file': bad})
        self.assertIn('not UTF-8', str(response.context['form'].errors['file']))

    def test_mapping_rejects_same_column_twice_and_missing_text(self):
        dataset = Dataset.objects.create(owner=self.user, name='Q1', source_filename='f.csv', raw_csv=SAMPLE)
        url = reverse('feedback:map_columns', args=[dataset.pk])
        response = self.client.post(url, {'text': 'reason', 'plan': 'reason'})
        self.assertContains(response, 'Each column can only be used once.')
        response = self.client.post(url, {'text': ''})
        self.assertTrue(response.context['form'].errors['text'])
        self.assertEqual(dataset.responses.count(), 0)


class DatasetFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana', password='pw-123456789')
        self.client.force_login(self.user)
        self.dataset = make_dataset(self.user)
        self.pricing = Theme.objects.create(dataset=self.dataset, name='Pricing')
        self.dataset.responses.filter(text__icontains='expensive').update(theme=self.pricing)
        self.dataset.responses.filter(text__icontains='price').update(theme=self.pricing)

    def test_dashboard_shows_aggregates(self):
        response = self.client.get(reverse('feedback:dataset_detail', args=[self.dataset.pk]))
        stats = response.context['stats']
        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['unassigned'], 2)
        self.assertEqual(stats['unassigned_percent'], 50.0)
        self.assertEqual(stats['themes'][0], {'id': self.pricing.pk, 'name': 'Pricing', 'count': 2, 'percent': 50.0})
        self.assertEqual(stats['months'], [{'month': '2026-01', 'count': 2}, {'month': '2026-02', 'count': 1}])
        self.assertEqual({p['plan']: p['count'] for p in stats['plans']}, {'Basic': 2, 'Pro': 2})

    def test_summary_api(self):
        url = reverse('feedback:api_dataset_summary', args=[self.dataset.pk])
        data = json.loads(self.client.get(url).content)
        self.assertEqual(data['dataset']['name'], 'Q1')
        self.assertEqual(data['total'], 4)
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_response_search_and_filters(self):
        url = reverse('feedback:response_list', args=[self.dataset.pk])
        self.assertEqual(self.client.get(url, {'q': 'sso'}).context['page'].paginator.count, 1)
        self.assertEqual(self.client.get(url, {'plan': 'Pro'}).context['page'].paginator.count, 2)
        self.assertEqual(self.client.get(url, {'theme': 'none'}).context['page'].paginator.count, 2)
        self.assertEqual(self.client.get(url, {'theme': self.pricing.pk}).context['page'].paginator.count, 2)

    def test_assign_theme_and_reject_foreign_theme(self):
        response_obj = self.dataset.responses.get(text='Missing SSO')
        url = reverse('feedback:assign_theme', args=[self.dataset.pk, response_obj.pk])
        self.client.post(url, {'theme': self.pricing.pk})
        response_obj.refresh_from_db()
        self.assertEqual(response_obj.theme, self.pricing)

        other = make_dataset(self.user, name='Other')
        foreign_theme = Theme.objects.create(dataset=other, name='Foreign')
        self.client.post(url, {'theme': foreign_theme.pk})
        response_obj.refresh_from_db()
        self.assertEqual(response_obj.theme, self.pricing, 'a theme from another dataset must be rejected')

    def test_assign_theme_ignores_offsite_next(self):
        response_obj = self.dataset.responses.first()
        url = reverse('feedback:assign_theme', args=[self.dataset.pk, response_obj.pk])
        response = self.client.post(url, {'theme': '', 'next': '//evil.example/'})
        self.assertRedirects(response, reverse('feedback:response_list', args=[self.dataset.pk]))

    def test_theme_create_rename_delete(self):
        create = reverse('feedback:theme_create', args=[self.dataset.pk])
        self.client.post(create, {'name': 'Bugs', 'description': ''})
        bugs = self.dataset.themes.get(name='Bugs')
        response = self.client.post(create, {'name': 'pricing'})
        self.assertFormError(response.context['form'], 'name', 'This dataset already has a theme with that name.')

        self.client.post(reverse('feedback:theme_edit', args=[self.dataset.pk, bugs.pk]), {'name': 'Technical issues'})
        bugs.refresh_from_db()
        self.assertEqual(bugs.name, 'Technical issues')

        self.client.post(reverse('feedback:theme_delete', args=[self.dataset.pk, bugs.pk]))
        self.assertFalse(Theme.objects.filter(pk=bugs.pk).exists())

    def test_export_csv(self):
        response = self.client.get(reverse('feedback:export_csv', args=[self.dataset.pk]))
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        lines = response.content.decode().strip().splitlines()
        self.assertEqual(lines[0], 'row_number,feedback,cancelled_on,plan,segment,theme,theme_confidence')
        self.assertEqual(len(lines), 5)
        self.assertIn('Pricing', lines[1])

    def test_edit_and_delete_dataset(self):
        self.client.post(reverse('feedback:dataset_edit', args=[self.dataset.pk]), {'name': 'Renamed', 'description': 'x'})
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.name, 'Renamed')
        self.client.post(reverse('feedback:dataset_delete', args=[self.dataset.pk]))
        self.assertFalse(Dataset.objects.filter(pk=self.dataset.pk).exists())

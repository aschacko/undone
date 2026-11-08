import csv

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, ListView, UpdateView

from .forms import (
    AssignThemeForm, ColumnMappingForm, DatasetEditForm, DatasetUploadForm, SignUpForm, ThemeForm,
)
from .models import Dataset, FeedbackResponse, Theme
from .services import CSVError, import_rows, parse_csv

RESPONSES_PER_PAGE = 25
# The text shown for responses with no theme, in charts, tables and the API.
UNASSIGNED_LABEL = 'Unassigned'


def owned_dataset(request, pk):
    """Return the user's dataset or 404.

    404 rather than 403 for other users' datasets, so ids cannot be probed.
    Every view that takes a dataset pk goes through here.
    """
    return get_object_or_404(Dataset, pk=pk, owner=request.user)


# --- Public pages and sign-up ----------------------------------------------

def home(request):
    if request.user.is_authenticated:
        return redirect('feedback:dataset_list')
    return render(request, 'feedback/home.html')


def signup(request):
    if request.user.is_authenticated:
        return redirect('feedback:dataset_list')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Welcome to Undone! Start by uploading a CSV of cancellation feedback.')
        return redirect('feedback:upload')
    return render(request, 'registration/signup.html', {'form': form})


# --- Datasets ----------------------------------------------------------------

class DatasetListView(LoginRequiredMixin, ListView):
    template_name = 'feedback/dataset_list.html'
    context_object_name = 'datasets'

    def get_queryset(self):
        return (
            Dataset.objects.filter(owner=self.request.user)
            .annotate(
                response_count=Count('responses', distinct=True),
                theme_count=Count('themes', distinct=True),
            )
        )


@login_required
def upload(request):
    """Step 1 of 2: validate the CSV and store it until columns are mapped."""
    form = DatasetUploadForm(request.POST or None, request.FILES or None, owner=request.user)
    if request.method == 'POST' and form.is_valid():
        dataset = Dataset.objects.create(
            owner=request.user,
            name=form.cleaned_data['name'],
            description=form.cleaned_data['description'],
            source_filename=form.cleaned_data['file'].name[:255],
            raw_csv=form.text,
        )
        messages.info(request, f'Read {len(form.rows):,} rows. Now tell us which column is which.')
        return redirect('feedback:map_columns', pk=dataset.pk)
    return render(request, 'feedback/upload.html', {'form': form, 'step': 1})


@login_required
def map_columns(request, pk):
    """Step 2 of 2: choose columns, preview, then import the rows."""
    dataset = owned_dataset(request, pk)
    if dataset.status != Dataset.Status.MAPPING:
        return redirect(dataset)
    try:
        headers, rows = parse_csv(dataset.raw_csv)
    except CSVError as exc:
        # Only possible if the stored text was damaged; start the upload again.
        messages.error(request, f'{exc} Please upload the file again.')
        dataset.delete()
        return redirect('feedback:upload')

    form = ColumnMappingForm(request.POST or None, headers=headers)
    if request.method == 'POST' and form.is_valid():
        try:
            result = import_rows(dataset, headers, rows, form.cleaned_data)
        except CSVError as exc:
            form.add_error('text', str(exc))
        else:
            messages.success(request, f'Imported {result.created:,} responses.')
            if result.skipped_empty:
                messages.warning(request, f'Skipped {result.skipped_empty:,} rows with empty feedback.')
            if result.unreadable_dates:
                shown = ', '.join(str(n) for n in result.unreadable_dates[:10])
                more = '…' if len(result.unreadable_dates) > 10 else ''
                messages.warning(
                    request,
                    f'{len(result.unreadable_dates):,} dates could not be read and were left blank '
                    f'(rows {shown}{more}). Use YYYY-MM-DD.',
                )
            return redirect(dataset)

    context = {
        'dataset': dataset,
        'form': form,
        'headers': headers,
        'preview_rows': rows[:5],
        'row_count': len(rows),
        'step': 2,
    }
    return render(request, 'feedback/map_columns.html', context)


def dataset_stats(dataset):
    """Aggregate counts used by both the dashboard page and the JSON API."""
    responses = dataset.responses.all()
    total = responses.count()

    by_theme = list(
        responses.values('theme_id', 'theme__name')
        .annotate(count=Count('id'))
        .order_by('-count', 'theme__name')
    )
    themes = [
        {
            'id': row['theme_id'],
            'name': row['theme__name'] or UNASSIGNED_LABEL,
            'count': row['count'],
            'percent': round(100 * row['count'] / total, 1) if total else 0,
        }
        for row in by_theme
    ]
    # Unassigned is not a reason, so it goes last however large it is (SQLite
    # would otherwise sort the NULL theme first on a tie).
    themes.sort(key=lambda t: t['id'] is None)
    by_plan = list(
        responses.exclude(plan='').values('plan').annotate(count=Count('id')).order_by('-count', 'plan')
    )
    by_month = [
        {'month': row['month'].strftime('%Y-%m'), 'count': row['count']}
        for row in responses.filter(cancelled_on__isnull=False)
        .annotate(month=TruncMonth('cancelled_on'))
        .values('month').annotate(count=Count('id')).order_by('month')
    ]
    unassigned = responses.filter(theme__isnull=True).count()
    return {
        'total': total,
        'theme_count': dataset.themes.count(),
        'unassigned': unassigned,
        'unassigned_percent': round(100 * unassigned / total, 1) if total else 0,
        'themes': themes,
        'plans': by_plan,
        'months': by_month,
    }


@login_required
def dataset_detail(request, pk):
    dataset = owned_dataset(request, pk)
    if dataset.status == Dataset.Status.MAPPING:
        return redirect(dataset)
    stats = dataset_stats(dataset)
    top_theme = next((t for t in stats['themes'] if t['id'] is not None), None)
    context = {
        'dataset': dataset,
        'stats': stats,
        'top_theme': top_theme,
        'theme_list': dataset.themes.annotate(count=Count('responses')),
        'samples': dataset.responses.select_related('theme')[:5],
    }
    return render(request, 'feedback/dataset_detail.html', context)


class OwnedDatasetMixin(LoginRequiredMixin):
    def get_queryset(self):
        return Dataset.objects.filter(owner=self.request.user)


class DatasetUpdateView(OwnedDatasetMixin, UpdateView):
    form_class = DatasetEditForm
    template_name = 'feedback/dataset_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Dataset updated.')
        return super().form_valid(form)


class DatasetDeleteView(OwnedDatasetMixin, DeleteView):
    template_name = 'feedback/confirm_delete.html'
    success_url = reverse_lazy('feedback:dataset_list')

    def form_valid(self, form):
        messages.success(self.request, f'Deleted "{self.object}" and all of its responses.')
        return super().form_valid(form)


# --- Responses ---------------------------------------------------------------

@login_required
def response_list(request, pk):
    """Search and filter one dataset's responses; reassign themes inline."""
    dataset = owned_dataset(request, pk)
    responses = dataset.responses.select_related('theme')

    query = request.GET.get('q', '').strip()
    plan = request.GET.get('plan', '')
    theme_param = request.GET.get('theme', '')
    current_theme = None

    if query:
        responses = responses.filter(Q(text__icontains=query) | Q(segment__icontains=query))
    if plan:
        responses = responses.filter(plan=plan)
    if theme_param == 'none':
        responses = responses.filter(theme__isnull=True)
    elif theme_param.isdigit():
        current_theme = get_object_or_404(Theme, pk=theme_param, dataset=dataset)
        responses = responses.filter(theme=current_theme)

    page = Paginator(responses, RESPONSES_PER_PAGE).get_page(request.GET.get('page'))
    # Keep filters when paging: the querystring minus the page number.
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'dataset': dataset,
        'page': page,
        'query': query,
        'plan': plan,
        'theme_param': theme_param,
        'current_theme': current_theme,
        'plans': dataset.responses.exclude(plan='').values_list('plan', flat=True).distinct().order_by('plan'),
        'themes': dataset.themes.all(),
        'filter_querystring': params.urlencode(),
    }
    return render(request, 'feedback/response_list.html', context)


@login_required
@require_POST
def assign_theme(request, pk, response_pk):
    dataset = owned_dataset(request, pk)
    response = get_object_or_404(FeedbackResponse, pk=response_pk, dataset=dataset)
    form = AssignThemeForm(request.POST, dataset=dataset)
    if form.is_valid():
        response.theme = form.cleaned_data['theme']
        response.theme_confidence = None  # a person decided, not the model
        response.save(update_fields=['theme', 'theme_confidence'])
        label = response.theme.name if response.theme else UNASSIGNED_LABEL
        messages.success(request, f'Row {response.row_number} moved to "{label}".')
    else:
        messages.error(request, 'That theme does not belong to this dataset.')
    next_url = request.POST.get('next', '')
    if next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect('feedback:response_list', pk=dataset.pk)


# --- Themes ------------------------------------------------------------------

@login_required
def theme_create(request, pk):
    dataset = owned_dataset(request, pk)
    form = ThemeForm(request.POST or None, dataset=dataset)
    if request.method == 'POST' and form.is_valid():
        theme = form.save(commit=False)
        theme.dataset = dataset
        theme.save()
        messages.success(request, f'Created theme "{theme}".')
        return redirect('feedback:dataset_detail', pk=dataset.pk)
    return render(request, 'feedback/theme_form.html', {'form': form, 'dataset': dataset})


@login_required
def theme_edit(request, pk, theme_pk):
    dataset = owned_dataset(request, pk)
    theme = get_object_or_404(Theme, pk=theme_pk, dataset=dataset)
    form = ThemeForm(request.POST or None, instance=theme, dataset=dataset)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Renamed theme to "{theme}".')
        return redirect('feedback:dataset_detail', pk=dataset.pk)
    return render(request, 'feedback/theme_form.html', {'form': form, 'dataset': dataset, 'theme': theme})


@login_required
def theme_delete(request, pk, theme_pk):
    dataset = owned_dataset(request, pk)
    theme = get_object_or_404(Theme, pk=theme_pk, dataset=dataset)
    if request.method == 'POST':
        count = theme.responses.count()
        theme.delete()
        messages.success(request, f'Deleted theme "{theme}". {count} responses are now unassigned.')
        return redirect('feedback:dataset_detail', pk=dataset.pk)
    context = {
        'object': theme,
        'dataset': dataset,
        'consequence': f'Its {theme.responses.count()} responses will become unassigned; they are not deleted.',
        'cancel_url': reverse('feedback:dataset_detail', args=[dataset.pk]),
    }
    return render(request, 'feedback/confirm_delete.html', context)


# --- Data out: CSV export and JSON API ---------------------------------------

@login_required
def export_csv(request, pk):
    dataset = owned_dataset(request, pk)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = ''.join(c if c.isalnum() or c in '-_' else '_' for c in dataset.name) or 'dataset'
    response['Content-Disposition'] = f'attachment; filename="{filename}_themes.csv"'
    writer = csv.writer(response)
    writer.writerow(['row_number', 'feedback', 'cancelled_on', 'plan', 'segment', 'theme', 'theme_confidence'])
    for r in dataset.responses.select_related('theme'):
        writer.writerow([
            r.row_number, r.text, r.cancelled_on or '', r.plan, r.segment,
            r.theme.name if r.theme else UNASSIGNED_LABEL,
            '' if r.theme_confidence is None else r.theme_confidence,
        ])
    return response


def api_dataset_summary(request, pk):
    """GET /api/datasets/<pk>/summary/ - JSON statistics for one dataset.

    Used by the dashboard charts. Answers 401 JSON (not a login redirect) when
    signed out, since the caller is JavaScript, not a person.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    dataset = Dataset.objects.filter(pk=pk, owner=request.user).first()
    if dataset is None:
        return JsonResponse({'error': 'Dataset not found.'}, status=404)
    payload = {
        'dataset': {
            'id': dataset.pk,
            'name': dataset.name,
            'status': dataset.status,
            'status_label': dataset.get_status_display(),
        },
        **dataset_stats(dataset),
    }
    return JsonResponse(payload)

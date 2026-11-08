from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm

from .models import Dataset, Theme
from .services import CSVError, decode_upload, parse_csv


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False, help_text='Optional.')

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email')


class DatasetUploadForm(forms.Form):
    """Step 1: name the dataset and choose a CSV file."""

    name = forms.CharField(max_length=120, label='Dataset name')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    file = forms.FileField(label='CSV file', help_text='UTF-8 CSV with a header row.')

    def __init__(self, *args, owner, **kwargs):
        self.owner = owner
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if Dataset.objects.filter(owner=self.owner, name__iexact=name).exists():
            raise forms.ValidationError('You already have a dataset with this name.')
        return name

    def clean_file(self):
        upload = self.cleaned_data['file']
        if not upload.name.lower().endswith('.csv'):
            raise forms.ValidationError('Please upload a .csv file.')
        if upload.size > settings.UPLOAD_MAX_BYTES:
            limit_mb = settings.UPLOAD_MAX_BYTES // (1024 * 1024)
            raise forms.ValidationError(f'The file is larger than {limit_mb} MB.')
        try:
            text = decode_upload(upload.read())
            self.headers, self.rows = parse_csv(text)
        except CSVError as exc:
            raise forms.ValidationError(str(exc))
        self.text = text
        return upload


class ColumnMappingForm(forms.Form):
    """Step 2: say which CSV column holds the feedback, date, plan and segment.

    Choices are the file's own headers, so the user picks rather than types.
    """

    text = forms.ChoiceField(label='Feedback text (required)')
    date = forms.ChoiceField(label='Cancellation date', required=False)
    plan = forms.ChoiceField(label='Subscription plan', required=False)
    segment = forms.ChoiceField(label='Other customer group', required=False)

    def __init__(self, *args, headers, **kwargs):
        super().__init__(*args, **kwargs)
        columns = [(h, h) for h in headers]
        self.fields['text'].choices = [('', 'Choose a column…')] + columns
        for name in ('date', 'plan', 'segment'):
            self.fields[name].choices = [('', '— not in this file —')] + columns
        if not self.is_bound:
            self.initial = guess_mapping(headers)

    def clean(self):
        cleaned = super().clean()
        chosen = [v for v in cleaned.values() if v]
        if len(chosen) != len(set(chosen)):
            raise forms.ValidationError('Each column can only be used once.')
        return cleaned


# Header words that suggest which field a column holds; used for defaults only.
_MAPPING_HINTS = {
    'text': ('feedback', 'reason', 'comment', 'text', 'response', 'why'),
    'date': ('date', 'cancel', 'when'),
    'plan': ('plan', 'tier', 'subscription'),
    'segment': ('segment', 'region', 'group', 'country', 'channel'),
}


def guess_mapping(headers):
    """Pre-select columns whose names look like each field (user can change)."""
    guess, used = {}, set()
    for field_name, hints in _MAPPING_HINTS.items():
        for header in headers:
            if header not in used and any(h in header.lower() for h in hints):
                guess[field_name] = header
                used.add(header)
                break
    return guess


class DatasetEditForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ('name', 'description')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        clash = Dataset.objects.filter(owner=self.instance.owner, name__iexact=name)
        if clash.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('You already have a dataset with this name.')
        return name


class ThemeForm(forms.ModelForm):
    class Meta:
        model = Theme
        fields = ('name', 'description')
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, dataset, **kwargs):
        self.dataset = dataset
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        clash = Theme.objects.filter(dataset=self.dataset, name__iexact=name)
        if clash.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This dataset already has a theme with that name.')
        return name


class AssignThemeForm(forms.Form):
    """Move one response into a theme, or back to unassigned (blank)."""

    theme = forms.ModelChoiceField(queryset=Theme.objects.none(), required=False)

    def __init__(self, *args, dataset, **kwargs):
        super().__init__(*args, **kwargs)
        # Only this dataset's themes are valid choices, which also stops a
        # crafted POST from assigning another dataset's theme.
        self.fields['theme'].queryset = dataset.themes.all()

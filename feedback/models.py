"""
Undone's data model.

    User 1──* Dataset 1──* FeedbackResponse *──0..1 Theme *──1 Dataset

A Dataset is one uploaded CSV of cancellation feedback, owned by one user.
Each CSV row becomes a FeedbackResponse. A Theme ("Pricing", "Missing
features") groups responses within one dataset; themes are created by hand
today and by the AI pattern-detection step later (Theme.source records which).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class Dataset(models.Model):
    class Status(models.TextChoices):
        # Uploaded, waiting for the user to say which column holds what.
        MAPPING = 'mapping', 'Needs column mapping'
        # Rows imported; no AI analysis has run yet.
        READY = 'ready', 'Awaiting analysis'
        ANALYZING = 'analyzing', 'Analyzing'
        ANALYZED = 'analyzed', 'Analyzed'
        FAILED = 'failed', 'Analysis failed'

    # CASCADE: a user's feedback data is theirs alone, so deleting the account
    # deletes their datasets rather than leaving orphaned customer text behind.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='datasets'
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    source_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.MAPPING)
    # The uploaded CSV text, kept only between upload and column mapping, then
    # cleared so the raw file is not stored twice.
    raw_csv = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_dataset_name_per_owner'),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        if self.status == self.Status.MAPPING:
            return reverse('feedback:map_columns', args=[self.pk])
        return reverse('feedback:dataset_detail', args=[self.pk])


class Theme(models.Model):
    class Source(models.TextChoices):
        MANUAL = 'manual', 'Created by a user'
        AI = 'ai', 'Detected by AI'

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='themes')
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['dataset', 'name'], name='unique_theme_name_per_dataset'),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('feedback:response_list', args=[self.dataset_id])}?theme={self.pk}"


class FeedbackResponse(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='responses')
    # 1-based data-row number in the original CSV, so a user can find the row.
    row_number = models.PositiveIntegerField()
    text = models.TextField()
    cancelled_on = models.DateField(null=True, blank=True)
    plan = models.CharField(max_length=80, blank=True)
    segment = models.CharField(max_length=80, blank=True)
    # SET_NULL: deleting a theme returns its responses to "unassigned" instead
    # of deleting customer feedback.
    theme = models.ForeignKey(
        Theme, on_delete=models.SET_NULL, null=True, blank=True, related_name='responses'
    )
    # How confident the AI was in the theme assignment (0-1); blank when a
    # person assigned the theme.
    theme_confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['row_number']
        indexes = [models.Index(fields=['dataset', 'theme'])]

    def __str__(self):
        return f'{self.dataset} #{self.row_number}'

    def clean(self):
        if self.theme_id and self.theme.dataset_id != self.dataset_id:
            raise ValidationError({'theme': 'Theme belongs to a different dataset.'})

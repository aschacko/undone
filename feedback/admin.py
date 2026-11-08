from django.contrib import admin

from .models import Dataset, FeedbackResponse, Theme


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'owner__username')


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'dataset', 'source')
    list_filter = ('source',)


@admin.register(FeedbackResponse)
class FeedbackResponseAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'row_number', 'plan', 'cancelled_on', 'theme')
    list_filter = ('plan', 'theme__source')
    search_fields = ('text',)

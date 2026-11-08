from django.urls import path

from . import views

app_name = 'feedback'

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('datasets/', views.DatasetListView.as_view(), name='dataset_list'),
    path('datasets/upload/', views.upload, name='upload'),
    path('datasets/<int:pk>/', views.dataset_detail, name='dataset_detail'),
    path('datasets/<int:pk>/map/', views.map_columns, name='map_columns'),
    path('datasets/<int:pk>/edit/', views.DatasetUpdateView.as_view(), name='dataset_edit'),
    path('datasets/<int:pk>/delete/', views.DatasetDeleteView.as_view(), name='dataset_delete'),
    path('datasets/<int:pk>/responses/', views.response_list, name='response_list'),
    path('datasets/<int:pk>/responses/<int:response_pk>/theme/', views.assign_theme, name='assign_theme'),
    path('datasets/<int:pk>/themes/new/', views.theme_create, name='theme_create'),
    path('datasets/<int:pk>/themes/<int:theme_pk>/edit/', views.theme_edit, name='theme_edit'),
    path('datasets/<int:pk>/themes/<int:theme_pk>/delete/', views.theme_delete, name='theme_delete'),
    path('datasets/<int:pk>/export.csv', views.export_csv, name='export_csv'),
    path('api/datasets/<int:pk>/summary/', views.api_dataset_summary, name='api_dataset_summary'),
]

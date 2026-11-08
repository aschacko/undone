from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # login/, logout/, password_change/ ... with templates in templates/registration/
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('feedback.urls')),
]

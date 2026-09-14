"""
URL configuration for stay_recon project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from accounts.views import dashboard, signup
from events.views import event_create, event_edit
from rooms.views import csv_map_columns, csv_preview, csv_upload

from .views import health, index

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
    path('healthz/', health, name='health'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', dashboard, name='dashboard'),
    path('signup/', signup, name='signup'),
    path('events/create/', event_create, name='event_create'),
    path('events/<int:pk>/edit/', event_edit, name='event_edit'),
    path('events/<int:event_pk>/rooms/upload/', csv_upload, name='rooms_upload'),
    path('events/<int:event_pk>/rooms/map/', csv_map_columns, name='rooms_map_columns'),
    path('events/<int:event_pk>/rooms/preview/', csv_preview, name='rooms_preview'),
]

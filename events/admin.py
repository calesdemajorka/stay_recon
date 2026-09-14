from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'organiser', 'start_date', 'end_date']
    search_fields = ['name']

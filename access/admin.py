from django.contrib import admin

from .models import AccessLink


@admin.register(AccessLink)
class AccessLinkAdmin(admin.ModelAdmin):
    list_display = ['event', 'role', 'label', 'is_revoked', 'created_at']

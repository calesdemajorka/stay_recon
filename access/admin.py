from django.contrib import admin

from .models import AccessLink, Participant, PendingListUpload, StaffMember


@admin.register(AccessLink)
class AccessLinkAdmin(admin.ModelAdmin):
    list_display = ['event', 'role', 'label', 'is_revoked', 'created_at']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['event', 'name', 'email']
    search_fields = ['name', 'email']


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['event', 'name', 'email']
    search_fields = ['name', 'email']


@admin.register(PendingListUpload)
class PendingListUploadAdmin(admin.ModelAdmin):
    list_display = ['event', 'organiser', 'role', 'created_at']

from django.contrib import admin

from .models import PendingUpload, Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'room_type', 'capacity', 'event']
    search_fields = ['room_number']


@admin.register(PendingUpload)
class PendingUploadAdmin(admin.ModelAdmin):
    list_display = ['event', 'organiser', 'created_at']

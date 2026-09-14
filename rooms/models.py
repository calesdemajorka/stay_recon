from django.conf import settings
from django.db import models
from django.db.models.functions import Lower, Trim

from events.models import Event


class Room(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=50)
    room_type = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('room_number')),
                'event',
                name='unique_room_number_per_event',
            ),
        ]

    def __str__(self):
        return f'{self.room_number} ({self.event})'


class PendingUpload(models.Model):
    organiser = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    headers = models.JSONField(default=list)
    raw_rows = models.JSONField(default=list)
    column_mapping = models.JSONField(default=dict)
    mapped_rows = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint('organiser', 'event', name='unique_pending_upload_per_organiser_event'),
        ]

    def __str__(self):
        return f'Pending upload for {self.event} by {self.organiser}'

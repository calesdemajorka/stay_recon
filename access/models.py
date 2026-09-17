from django.db import models

from events.models import Event


class AccessLink(models.Model):
    ROLE_PARTICIPANT = 'participant'
    ROLE_STAFF = 'staff'
    ROLE_CHOICES = [
        (ROLE_PARTICIPANT, 'Participant'),
        (ROLE_STAFF, 'Staff'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='access_links')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    label = models.CharField(max_length=255)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_role_display()} link for {self.label} ({self.event})'

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower, Trim

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


class Participant(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participants')
    access_link = models.OneToOneField(AccessLink, on_delete=models.CASCADE, related_name='participant')
    name = models.CharField(max_length=255)
    email = models.EmailField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('email')),
                'event',
                name='unique_participant_email_per_event',
            ),
        ]

    def clean(self):
        # access_link is a separate FK with no DB-level link tying its
        # event/role/label to this row — plain .create()/.save() calls
        # never trigger this (Django only calls clean() via ModelForm,
        # e.g. the admin), so application code creating these rows must
        # still derive event/role/label from this row rather than
        # accepting an independently-picked AccessLink.
        if not self.access_link_id:
            return
        if self.event_id and self.access_link.event_id != self.event_id:
            raise ValidationError('Access link must belong to the same event as the participant.')
        if self.access_link.role != AccessLink.ROLE_PARTICIPANT:
            raise ValidationError('Access link must have the participant role.')
        if self.email and self.access_link.label != self.email:
            raise ValidationError("Access link label must match the participant's email.")

    def __str__(self):
        return f'{self.name} <{self.email}> ({self.event})'


class StaffMember(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='staff_members')
    access_link = models.OneToOneField(AccessLink, on_delete=models.CASCADE, related_name='staff_member')
    name = models.CharField(max_length=255)
    email = models.EmailField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('email')),
                'event',
                name='unique_staff_member_email_per_event',
            ),
        ]

    def clean(self):
        # See Participant.clean() — same cross-field invariants (event,
        # role, label), same caveat about plain .create()/.save() not
        # triggering this automatically.
        if not self.access_link_id:
            return
        if self.event_id and self.access_link.event_id != self.event_id:
            raise ValidationError('Access link must belong to the same event as the staff member.')
        if self.access_link.role != AccessLink.ROLE_STAFF:
            raise ValidationError('Access link must have the staff role.')
        if self.email and self.access_link.label != self.email:
            raise ValidationError("Access link label must match the staff member's email.")

    def __str__(self):
        return f'{self.name} <{self.email}> ({self.event})'


class PendingListUpload(models.Model):
    organiser = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=AccessLink.ROLE_CHOICES)
    rows = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                'organiser', 'event', 'role',
                name='unique_pending_list_upload_per_organiser_event_role',
            ),
        ]

    def __str__(self):
        return f'Pending {self.role} list upload for {self.event} by {self.organiser}'

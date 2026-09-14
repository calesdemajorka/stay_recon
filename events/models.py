from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower, Trim


class Event(models.Model):
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events',
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True, default='')
    window_start = models.DateField()
    window_end = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('name')),
                'start_date',
                'end_date',
                'organiser',
                name='unique_event_name_dates_per_organiser',
            ),
        ]

    def clean(self):
        # Model.clean() runs unconditionally from ModelForm._post_clean(),
        # even when a form field (e.g. an unparseable date) already failed
        # validation and left its instance attribute as None — guard every
        # comparison so that case surfaces as a normal form error, not a
        # TypeError crash.
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError('End date cannot be before start date.')
        if self.window_start and self.window_end and self.window_start > self.window_end:
            raise ValidationError('Booking window start cannot be after window end.')
        if self.window_end and self.start_date and self.window_end > self.start_date:
            raise ValidationError('Booking window must close by the event start date.')

    def __str__(self):
        return f'{self.name} ({self.start_date})'

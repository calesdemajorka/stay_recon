from datetime import timedelta

from django import forms
from django.db.models.functions import Lower, Trim

from .models import Event

DUPLICATE_ERROR = 'An event with this name and these dates already exists.'


class EventForm(forms.ModelForm):
    window_start = forms.DateField(required=False)
    window_end = forms.DateField(required=False)

    class Meta:
        model = Event
        fields = ('name', 'start_date', 'end_date', 'description', 'window_start', 'window_end')

    def __init__(self, *args, organiser=None, **kwargs):
        self.organiser = organiser
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        window_start = cleaned_data.get('window_start')
        window_end = cleaned_data.get('window_end')

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('End date cannot be before start date.')

        if start_date:
            if window_start is None:
                window_start = start_date - timedelta(days=14)
                cleaned_data['window_start'] = window_start
            if window_end is None:
                window_end = start_date - timedelta(days=3)
                cleaned_data['window_end'] = window_end

        if window_start and window_end and window_start > window_end:
            raise forms.ValidationError('Booking window start cannot be after window end.')
        if window_end and start_date and window_end > start_date:
            raise forms.ValidationError('Booking window must close by the event start date.')

        name = cleaned_data.get('name')
        if name and start_date and end_date and self.organiser is not None:
            duplicates = Event.objects.annotate(
                normalized_name=Lower(Trim('name'))
            ).filter(
                organiser=self.organiser,
                normalized_name=name.strip().lower(),
                start_date=start_date,
                end_date=end_date,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error('name', DUPLICATE_ERROR)

        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=False)
        event.window_start = self.cleaned_data['window_start']
        event.window_end = self.cleaned_data['window_end']
        if self.organiser is not None:
            event.organiser = self.organiser
        if commit:
            event.save()
        return event

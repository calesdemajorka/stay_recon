from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Event

User = get_user_model()


def make_event(**overrides):
    defaults = {
        'name': 'Team Offsite',
        'start_date': date(2026, 10, 1),
        'end_date': date(2026, 10, 2),
        'window_start': date(2026, 9, 17),
        'window_end': date(2026, 9, 28),
    }
    defaults.update(overrides)
    return Event.objects.create(**defaults)


class EventModelTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')

    def test_duplicate_normalized_name_and_dates_same_organiser_rejected(self):
        make_event(organiser=self.organiser)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_event(organiser=self.organiser, name='team offsite ')

    def test_same_name_and_dates_different_organisers_allowed(self):
        make_event(organiser=self.organiser)
        make_event(organiser=self.other_organiser)
        self.assertEqual(Event.objects.count(), 2)


class EventCreateViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.client.login(username='organiser@example.com', password='testpass123')

    def _post(self, **overrides):
        data = {
            'name': 'Team Offsite',
            'start_date': '2026-10-01',
            'end_date': '2026-10-02',
            'description': '',
        }
        data.update(overrides)
        return self.client.post(reverse('event_create'), data)

    def test_valid_submission_computes_window_defaults(self):
        response = self._post()
        self.assertRedirects(response, reverse('dashboard'))
        event = Event.objects.get()
        self.assertEqual(event.window_start, date(2026, 10, 1) - timedelta(days=14))
        self.assertEqual(event.window_end, date(2026, 10, 1) - timedelta(days=3))
        self.assertEqual(event.organiser, self.organiser)

    def test_valid_submission_with_explicit_window_keeps_values(self):
        response = self._post(window_start='2026-09-20', window_end='2026-09-25')
        self.assertRedirects(response, reverse('dashboard'))
        event = Event.objects.get()
        self.assertEqual(event.window_start, date(2026, 9, 20))
        self.assertEqual(event.window_end, date(2026, 9, 25))

    def test_duplicate_submission_shows_error_creates_no_row(self):
        make_event(
            organiser=self.organiser,
            window_start=date(2026, 9, 17),
            window_end=date(2026, 9, 28),
        )
        response = self._post(name='team offsite ')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'name', 'An event with this name and these dates already exists.'
        )
        self.assertEqual(Event.objects.count(), 1)

    def test_end_date_before_start_date_rejected(self):
        response = self._post(start_date='2026-10-05', end_date='2026-10-01')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertEqual(Event.objects.count(), 0)

    def test_window_end_after_start_date_rejected(self):
        response = self._post(window_start='2026-09-20', window_end='2026-10-02')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertEqual(Event.objects.count(), 0)

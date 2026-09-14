from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

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

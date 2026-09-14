from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from events.models import Event

from .models import PendingUpload, Room

User = get_user_model()


def make_event(**overrides):
    organiser = overrides.pop('organiser')
    defaults = {
        'name': 'Room Test Event',
        'start_date': date(2026, 12, 1),
        'end_date': date(2026, 12, 2),
        'window_start': date(2026, 11, 17),
        'window_end': date(2026, 11, 28),
    }
    defaults.update(overrides)
    return Event.objects.create(organiser=organiser, **defaults)


class RoomModelTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.other_event = make_event(organiser=self.organiser, name='Other Event', start_date=date(2027, 1, 1), end_date=date(2027, 1, 2), window_start=date(2026, 12, 18), window_end=date(2026, 12, 29))

    def test_duplicate_room_number_same_event_rejected(self):
        Room.objects.create(event=self.event, room_number='101', room_type='Single', capacity=2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(event=self.event, room_number=' 101 ', room_type='Double', capacity=3)

    def test_same_room_number_different_events_allowed(self):
        Room.objects.create(event=self.event, room_number='101', room_type='Single', capacity=2)
        Room.objects.create(event=self.other_event, room_number='101', room_type='Single', capacity=2)
        self.assertEqual(Room.objects.count(), 2)


class PendingUploadModelTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)

    def test_json_fields_round_trip(self):
        pending = PendingUpload.objects.create(
            organiser=self.organiser,
            event=self.event,
            headers=['Room No', 'Type', 'Cap'],
            raw_rows=[{'Room No': '101', 'Type': 'Single', 'Cap': '2'}],
            column_mapping={'room_number': 'Room No', 'room_type': 'Type', 'capacity': 'Cap'},
            mapped_rows=[{'room_number': '101', 'room_type': 'Single', 'capacity': '2', 'errors': {}}],
        )
        pending.refresh_from_db()
        self.assertEqual(pending.headers, ['Room No', 'Type', 'Cap'])
        self.assertEqual(pending.raw_rows[0]['Room No'], '101')
        self.assertEqual(pending.column_mapping['room_number'], 'Room No')
        self.assertEqual(pending.mapped_rows[0]['room_number'], '101')

    def test_unique_per_organiser_event(self):
        PendingUpload.objects.create(organiser=self.organiser, event=self.event)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingUpload.objects.create(organiser=self.organiser, event=self.event)

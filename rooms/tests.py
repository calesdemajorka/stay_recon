import io
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from events.models import Event

from .forms import MAX_ROWS
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


class CSVUploadViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _upload(self, content_bytes, filename='rooms.csv', **extra):
        data = {'csv_file': SimpleUploadedFile(filename, content_bytes)}
        data.update(extra)
        return self.client.post(reverse('rooms_upload', args=[self.event.pk]), data)

    def test_valid_utf8_csv_creates_pending_upload(self):
        csv_bytes = 'Room No,Type,Cap\n101,Single,2\n102,Double,3\n'.encode('utf-8')
        response = self._upload(csv_bytes)
        self.assertRedirects(response, reverse('rooms_map_columns', args=[self.event.pk]))
        pending = PendingUpload.objects.get(organiser=self.organiser, event=self.event)
        self.assertEqual(pending.headers, ['Room No', 'Type', 'Cap'])
        self.assertEqual(pending.raw_rows[0]['Room No'], '101')

    def test_bom_stripped_from_first_header(self):
        csv_bytes = 'Room No,Type,Cap\n101,Single,2\n'.encode('utf-8-sig')
        self._upload(csv_bytes)
        pending = PendingUpload.objects.get(organiser=self.organiser, event=self.event)
        self.assertEqual(pending.headers[0], 'Room No')

    def test_cp1252_csv_decoded_via_fallback(self):
        csv_text = 'Room No,Type,Cap\n101,Suite – Deluxe,2\n'
        csv_bytes = csv_text.encode('cp1252')
        self._upload(csv_bytes)
        pending = PendingUpload.objects.get(organiser=self.organiser, event=self.event)
        self.assertEqual(pending.raw_rows[0]['Type'], 'Suite – Deluxe')

    def test_second_upload_replaces_existing_pending_upload(self):
        self._upload('Room No,Type,Cap\n101,Single,2\n'.encode('utf-8'))
        self._upload('Room No,Type,Cap\n201,Double,4\n'.encode('utf-8'))
        self.assertEqual(PendingUpload.objects.filter(organiser=self.organiser, event=self.event).count(), 1)
        pending = PendingUpload.objects.get(organiser=self.organiser, event=self.event)
        self.assertEqual(pending.raw_rows[0]['Room No'], '201')

    def test_upload_for_event_with_confirmed_rooms_rejected_without_confirm(self):
        Room.objects.create(event=self.event, room_number='101', room_type='Single', capacity=2)
        response = self._upload('Room No,Type,Cap\n201,Double,4\n'.encode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'confirm_replace', response.context['form'].errors['confirm_replace'])
        self.assertFalse(PendingUpload.objects.filter(organiser=self.organiser, event=self.event).exists())

    def test_upload_with_confirm_replace_checked_succeeds(self):
        Room.objects.create(event=self.event, room_number='101', room_type='Single', capacity=2)
        response = self._upload('Room No,Type,Cap\n201,Double,4\n'.encode('utf-8'), confirm_replace='on')
        self.assertRedirects(response, reverse('rooms_map_columns', args=[self.event.pk]))
        self.assertTrue(PendingUpload.objects.filter(organiser=self.organiser, event=self.event).exists())

    def test_upload_for_another_organisers_event_returns_404(self):
        other_event = make_event(organiser=self.other_organiser, name='Other', start_date=date(2027, 2, 1), end_date=date(2027, 2, 2), window_start=date(2027, 1, 18), window_end=date(2027, 1, 29))
        response = self.client.post(
            reverse('rooms_upload', args=[other_event.pk]),
            {'csv_file': SimpleUploadedFile('rooms.csv', b'Room No,Type,Cap\n101,Single,2\n')},
        )
        self.assertEqual(response.status_code, 404)

    def test_non_csv_binary_upload_rejected(self):
        # Simulates a wrong-file-type upload (e.g. .xlsx renamed .csv): a
        # long run of bytes with no comma/newline, decoding via the latin-1
        # fallback into one implausibly-long "header" rather than raising.
        garbage = b'\x00\x01\x02\x03\xff\xfe' * 100
        response = self._upload(garbage, filename='not-a-csv.bin')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PendingUpload.objects.filter(organiser=self.organiser, event=self.event).exists())


class ColumnMappingViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.pending = PendingUpload.objects.create(
            organiser=self.organiser,
            event=self.event,
            headers=['Room No', 'Type', 'Cap'],
            raw_rows=[
                {'Room No': '101', 'Type': 'Single', 'Cap': '2'},
                {'Room No': '', 'Type': 'Double', 'Cap': '3'},
                {'Room No': '103', 'Type': 'Suite', 'Cap': 'four'},
            ],
        )
        self.client.login(username='organiser@example.com', password='testpass123')

    def test_form_populated_with_actual_headers(self):
        response = self.client.get(reverse('rooms_map_columns', args=[self.event.pk]))
        choices = response.context['form'].fields['room_number'].choices
        self.assertEqual([c[0] for c in choices], ['Room No', 'Type', 'Cap'])

    def test_submitting_mapping_computes_mapped_rows(self):
        response = self.client.post(reverse('rooms_map_columns', args=[self.event.pk]), {
            'room_number': 'Room No', 'room_type': 'Type', 'capacity': 'Cap',
        })
        self.assertRedirects(response, reverse('rooms_preview', args=[self.event.pk]))
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.mapped_rows[0]['room_number'], '101')
        self.assertEqual(self.pending.mapped_rows[0]['room_type'], 'Single')
        self.assertEqual(self.pending.mapped_rows[0]['capacity'], '2')

    def test_missing_room_number_flagged(self):
        self.client.post(reverse('rooms_map_columns', args=[self.event.pk]), {
            'room_number': 'Room No', 'room_type': 'Type', 'capacity': 'Cap',
        })
        self.pending.refresh_from_db()
        self.assertIn('room_number', self.pending.mapped_rows[1]['errors'])

    def test_non_numeric_capacity_flagged(self):
        self.client.post(reverse('rooms_map_columns', args=[self.event.pk]), {
            'room_number': 'Room No', 'room_type': 'Type', 'capacity': 'Cap',
        })
        self.pending.refresh_from_db()
        self.assertIn('capacity', self.pending.mapped_rows[2]['errors'])

    def test_valid_row_has_empty_errors(self):
        self.client.post(reverse('rooms_map_columns', args=[self.event.pk]), {
            'room_number': 'Room No', 'room_type': 'Type', 'capacity': 'Cap',
        })
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.mapped_rows[0]['errors'], {})

    def test_mapping_for_another_organisers_data_returns_404(self):
        self.client.login(username='other@example.com', password='testpass123')
        response = self.client.get(reverse('rooms_map_columns', args=[self.event.pk]))
        self.assertEqual(response.status_code, 404)

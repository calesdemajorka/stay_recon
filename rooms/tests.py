import io
from datetime import date
from unittest import mock

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

    def test_deleting_event_cascades_to_its_rooms(self):
        Room.objects.create(event=self.event, room_number='101', room_type='Single', capacity=2)
        self.event.delete()
        self.assertEqual(Room.objects.count(), 0)


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


def _row(room_number, room_type='Single', capacity='2', errors=None):
    return {'room_number': room_number, 'room_type': room_type, 'capacity': capacity, 'errors': errors or {}}


def _formset_post_data(rows, current_page, action):
    data = {
        'form-TOTAL_FORMS': str(len(rows)),
        'form-INITIAL_FORMS': str(len(rows)),
        'form-MIN_NUM_FORMS': '0',
        'form-MAX_NUM_FORMS': '1000',
        'current_page': str(current_page),
        'action': action,
    }
    for i, row in enumerate(rows):
        data[f'form-{i}-room_number'] = row['room_number']
        data[f'form-{i}-room_type'] = row['room_type']
        data[f'form-{i}-capacity'] = row['capacity']
    return data


class PreviewConfirmViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _make_pending(self, mapped_rows):
        return PendingUpload.objects.create(
            organiser=self.organiser, event=self.event, headers=[], raw_rows=[], mapped_rows=mapped_rows,
        )

    def test_page_slices_correct(self):
        rows = [_row(str(100 + i)) for i in range(30)]
        self._make_pending(rows)
        response = self.client.get(reverse('rooms_preview', args=[self.event.pk]), {'page': 2})
        self.assertEqual(response.context['page'], 2)
        self.assertEqual(response.context['total_pages'], 2)
        self.assertEqual(len(response.context['rows']), 5)

    def test_correcting_row_clears_error_and_persists(self):
        pending = self._make_pending([_row('101', capacity='bad', errors={'capacity': 'Capacity must be a whole number.'})])
        data = _formset_post_data([_row('101', capacity='4')], current_page=1, action='next')
        self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        pending.refresh_from_db()
        self.assertEqual(pending.mapped_rows[0]['errors'], {})
        self.assertEqual(pending.mapped_rows[0]['capacity'], '4')

    def test_cross_page_duplicate_not_flagged_by_page_save(self):
        # 30 rows: page 1 = rows[0:25] (includes '101' at index 0),
        # page 2 = rows[25:30] (5 rows).
        rows = [_row('101')] + [_row(str(200 + i)) for i in range(29)]
        pending = self._make_pending(rows)
        page2_rows = pending.mapped_rows[25:30]
        page2_rows[0] = _row('101')
        data = _formset_post_data(page2_rows, current_page=2, action='next')
        response = self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 302)
        pending.refresh_from_db()
        self.assertEqual(pending.mapped_rows[25]['errors'], {})

    def test_confirm_blocks_on_remaining_error(self):
        pending = self._make_pending([_row('101'), _row('', errors={'room_number': 'Room number is required.'})])
        data = _formset_post_data(pending.mapped_rows, current_page=1, action='confirm')
        response = self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context['page_error'])
        self.assertEqual(Room.objects.count(), 0)

    def test_confirm_blocks_on_cross_page_duplicate(self):
        rows = [_row('101')] + [_row(str(200 + i)) for i in range(29)]
        pending = self._make_pending(rows)
        page2_rows = pending.mapped_rows[25:30]
        page2_rows[0] = _row('101')
        pending.mapped_rows[25:30] = page2_rows
        pending.save()
        data = _formset_post_data(page2_rows, current_page=2, action='confirm')
        response = self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('duplicates', response.context['page_error'])
        self.assertEqual(Room.objects.count(), 0)

    def test_confirm_with_valid_data_creates_rooms(self):
        pending = self._make_pending([_row('101'), _row('102', capacity='3')])
        data = _formset_post_data(pending.mapped_rows, current_page=1, action='confirm')
        response = self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertRedirects(response, reverse('event_edit', args=[self.event.pk]))
        self.assertEqual(Room.objects.filter(event=self.event).count(), 2)
        self.assertFalse(PendingUpload.objects.filter(pk=pending.pk).exists())

    def test_replace_flow_confirm_is_atomic(self):
        Room.objects.create(event=self.event, room_number='OLD', room_type='Single', capacity=1)
        pending = self._make_pending([_row('101')])
        data = _formset_post_data(pending.mapped_rows, current_page=1, action='confirm')
        with mock.patch('rooms.views.Room.objects.bulk_create', side_effect=Exception('boom')):
            with self.assertRaises(Exception):
                self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertEqual(Room.objects.filter(event=self.event).count(), 1)
        self.assertEqual(Room.objects.get(event=self.event).room_number, 'OLD')

    def test_preview_for_another_organisers_data_returns_404(self):
        self._make_pending([_row('101')])
        self.client.login(username='other@example.com', password='testpass123')
        response = self.client.get(reverse('rooms_preview', args=[self.event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_mismatched_total_forms_rejected(self):
        pending = self._make_pending([_row('101'), _row('102')])
        data = _formset_post_data([_row('101')], current_page=1, action='next')
        data['form-TOTAL_FORMS'] = '1'  # actual page has 2 rows
        response = self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('went wrong', response.context['page_error'])
        pending.refresh_from_db()
        self.assertEqual(len(pending.mapped_rows), 2)

    def test_confirm_with_empty_mapped_rows_blocked(self):
        self._make_pending([])
        data = _formset_post_data([], current_page=1, action='confirm')
        response = self.client.post(reverse('rooms_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('No rows found', response.context['page_error'])
        self.assertEqual(Room.objects.count(), 0)

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event

from .forms import MAX_UPLOAD_BYTES
from .models import AccessLink, Participant, PendingListUpload, StaffMember
from .services import STAFF_SESSION_KEY, verify_access_link

User = get_user_model()


def make_event(**overrides):
    organiser = overrides.pop('organiser')
    defaults = {
        'name': 'Access Link Test Event',
        'start_date': date(2026, 12, 1),
        'end_date': date(2026, 12, 2),
        'window_start': date(2026, 11, 17),
        'window_end': date(2026, 11, 28),
    }
    defaults.update(overrides)
    return Event.objects.create(organiser=organiser, **defaults)


def make_access_link(**overrides):
    defaults = {
        'role': AccessLink.ROLE_PARTICIPANT,
        'label': 'jane@example.com',
        'token': 'test-token',
        'is_revoked': False,
    }
    defaults.update(overrides)
    return AccessLink.objects.create(**defaults)


def make_participant(**overrides):
    event = overrides.pop('event')
    token = overrides.pop('token', f'participant-token-{Participant.objects.count()}')
    access_link = make_access_link(event=event, role=AccessLink.ROLE_PARTICIPANT, token=token,
                                    label=overrides.get('email', 'jane@example.com'))
    defaults = {'event': event, 'access_link': access_link, 'name': 'Jane Doe', 'email': 'jane@example.com'}
    defaults.update(overrides)
    return Participant.objects.create(**defaults)


def make_staff_member(**overrides):
    event = overrides.pop('event')
    token = overrides.pop('token', f'staff-token-{StaffMember.objects.count()}')
    access_link = make_access_link(event=event, role=AccessLink.ROLE_STAFF, token=token,
                                    label=overrides.get('email', 'sam@example.com'))
    defaults = {'event': event, 'access_link': access_link, 'name': 'Sam Staff', 'email': 'sam@example.com'}
    defaults.update(overrides)
    return StaffMember.objects.create(**defaults)


class AccessLinkModelTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)

    def test_multiple_access_links_per_event_allowed(self):
        make_access_link(event=self.event, token='token-1', label='a@example.com')
        make_access_link(event=self.event, token='token-2', label='b@example.com')
        self.assertEqual(AccessLink.objects.filter(event=self.event).count(), 2)

    def test_duplicate_token_rejected(self):
        make_access_link(event=self.event, token='shared-token')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_access_link(event=self.event, token='shared-token', label='other@example.com')

    def test_deleting_event_cascades_to_its_access_links(self):
        make_access_link(event=self.event, token='cascade-token')
        self.event.delete()
        self.assertFalse(AccessLink.objects.filter(token='cascade-token').exists())


class ParticipantStaffMemberModelTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.other_event = make_event(organiser=self.organiser, name='Other Event')

    def test_duplicate_participant_email_same_event_rejected(self):
        make_participant(event=self.event, email='a@example.com', token='p-1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_participant(event=self.event, email='A@Example.com ', token='p-2')

    def test_same_participant_email_different_events_allowed(self):
        make_participant(event=self.event, email='a@example.com', token='p-1')
        make_participant(event=self.other_event, email='a@example.com', token='p-2')
        self.assertEqual(Participant.objects.filter(email__iexact='a@example.com').count(), 2)

    def test_duplicate_staff_member_email_same_event_rejected(self):
        make_staff_member(event=self.event, email='a@example.com', token='s-1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_staff_member(event=self.event, email='A@Example.com ', token='s-2')

    def test_same_staff_member_email_different_events_allowed(self):
        make_staff_member(event=self.event, email='a@example.com', token='s-1')
        make_staff_member(event=self.other_event, email='a@example.com', token='s-2')
        self.assertEqual(StaffMember.objects.filter(email__iexact='a@example.com').count(), 2)

    def test_participant_clean_rejects_mismatched_access_link_event(self):
        mismatched_link = make_access_link(event=self.other_event, role=AccessLink.ROLE_PARTICIPANT, token='mismatch')
        participant = Participant(event=self.event, access_link=mismatched_link, name='Jane', email='jane@example.com')
        with self.assertRaises(ValidationError):
            participant.full_clean()

    def test_staff_member_clean_rejects_mismatched_access_link_event(self):
        mismatched_link = make_access_link(event=self.other_event, role=AccessLink.ROLE_STAFF, token='mismatch-2')
        staff = StaffMember(event=self.event, access_link=mismatched_link, name='Sam', email='sam@example.com')
        with self.assertRaises(ValidationError):
            staff.full_clean()

    def test_participant_clean_rejects_staff_role_access_link(self):
        staff_role_link = make_access_link(event=self.event, role=AccessLink.ROLE_STAFF, token='wrong-role', label='jane@example.com')
        participant = Participant(event=self.event, access_link=staff_role_link, name='Jane', email='jane@example.com')
        with self.assertRaises(ValidationError):
            participant.full_clean()

    def test_staff_member_clean_rejects_participant_role_access_link(self):
        participant_role_link = make_access_link(event=self.event, role=AccessLink.ROLE_PARTICIPANT, token='wrong-role-2', label='sam@example.com')
        staff = StaffMember(event=self.event, access_link=participant_role_link, name='Sam', email='sam@example.com')
        with self.assertRaises(ValidationError):
            staff.full_clean()

    def test_participant_clean_rejects_label_not_matching_email(self):
        mislabeled_link = make_access_link(event=self.event, role=AccessLink.ROLE_PARTICIPANT, token='bad-label', label='someone-else@example.com')
        participant = Participant(event=self.event, access_link=mislabeled_link, name='Jane', email='jane@example.com')
        with self.assertRaises(ValidationError):
            participant.full_clean()

    def test_staff_member_clean_rejects_label_not_matching_email(self):
        mislabeled_link = make_access_link(event=self.event, role=AccessLink.ROLE_STAFF, token='bad-label-2', label='someone-else@example.com')
        staff = StaffMember(event=self.event, access_link=mislabeled_link, name='Sam', email='sam@example.com')
        with self.assertRaises(ValidationError):
            staff.full_clean()


class PendingListUploadModelTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)

    def test_unique_per_organiser_event_role(self):
        PendingListUpload.objects.create(
            organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT,
            rows=[{'name': 'Jane', 'email': 'jane@example.com', 'errors': {}}],
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendingListUpload.objects.create(
                    organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT, rows=[],
                )

    def test_different_roles_coexist_independently(self):
        PendingListUpload.objects.create(
            organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT, rows=[],
        )
        PendingListUpload.objects.create(
            organiser=self.organiser, event=self.event, role=AccessLink.ROLE_STAFF, rows=[],
        )
        self.assertEqual(PendingListUpload.objects.filter(event=self.event).count(), 2)


class VerifyAccessLinkTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)

    def test_valid_token_resolves(self):
        link = make_access_link(event=self.event, token='valid-token')
        self.assertEqual(verify_access_link('valid-token'), link)

    def test_unknown_token_returns_none(self):
        self.assertIsNone(verify_access_link('does-not-exist'))

    def test_revoked_token_returns_none(self):
        make_access_link(event=self.event, token='revoked-token', is_revoked=True)
        self.assertIsNone(verify_access_link('revoked-token'))

    def test_expired_token_returns_none(self):
        expired_event = make_event(
            organiser=self.organiser,
            name='Past Event',
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 2),
            window_start=date(2019, 12, 1),
            window_end=timezone.now().date() - timedelta(days=1),
        )
        make_access_link(event=expired_event, token='expired-token')
        self.assertIsNone(verify_access_link('expired-token'))

    def test_wrong_role_rejected(self):
        make_access_link(event=self.event, token='staff-token', role=AccessLink.ROLE_STAFF)
        self.assertIsNone(verify_access_link('staff-token', role=AccessLink.ROLE_PARTICIPANT))


class ParticipantAccessViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)

    def test_valid_token_shows_event_name(self):
        make_access_link(event=self.event, token='valid-token', label='jane@example.com')
        response = self.client.get(reverse('participant_access', args=['valid-token']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.name)
        self.assertContains(response, 'jane@example.com')

    def test_invalid_token_shows_invalid_message(self):
        response = self.client.get(reverse('participant_access', args=['no-such-token']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')

    def test_staff_token_rejected_on_participant_url(self):
        make_access_link(event=self.event, token='staff-token', role=AccessLink.ROLE_STAFF)
        response = self.client.get(reverse('participant_access', args=['staff-token']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')


class StaffSessionTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.event_a = make_event(organiser=self.organiser, name='Event A')
        self.event_b = make_event(organiser=self.organiser, name='Event B')

    def test_valid_staff_token_establishes_session_and_redirects(self):
        make_access_link(event=self.event_a, token='staff-token', role=AccessLink.ROLE_STAFF)
        response = self.client.get(reverse('staff_login', args=['staff-token']))
        self.assertRedirects(response, reverse('staff_dashboard', args=[self.event_a.pk]))
        self.assertEqual(self.client.session[STAFF_SESSION_KEY], AccessLink.objects.get(token='staff-token').pk)

    def test_participant_token_rejected_on_staff_login(self):
        make_access_link(event=self.event_a, token='participant-token', role=AccessLink.ROLE_PARTICIPANT)
        response = self.client.get(reverse('staff_login', args=['participant-token']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')
        self.assertNotIn(STAFF_SESSION_KEY, self.client.session)

    def test_second_request_succeeds_via_session_alone(self):
        link = make_access_link(event=self.event_a, token='staff-token', role=AccessLink.ROLE_STAFF)
        self.client.get(reverse('staff_login', args=['staff-token']))
        response = self.client.get(reverse('staff_dashboard', args=[self.event_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event_a.name)
        self.assertContains(response, link.label)

    def test_session_for_one_event_rejected_on_another(self):
        make_access_link(event=self.event_a, token='staff-token', role=AccessLink.ROLE_STAFF)
        self.client.get(reverse('staff_login', args=['staff-token']))
        response = self.client.get(reverse('staff_dashboard', args=[self.event_b.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')

    def test_revoking_link_after_session_established_fails_next_request(self):
        link = make_access_link(event=self.event_a, token='staff-token', role=AccessLink.ROLE_STAFF)
        self.client.get(reverse('staff_login', args=['staff-token']))
        link.is_revoked = True
        link.save(update_fields=['is_revoked'])
        response = self.client.get(reverse('staff_dashboard', args=[self.event_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')

    def test_no_prior_session_shows_invalid_message(self):
        response = self.client.get(reverse('staff_dashboard', args=[self.event_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')

    def test_nonexistent_event_shows_invalid_message_not_404(self):
        make_access_link(event=self.event_a, token='staff-token', role=AccessLink.ROLE_STAFF)
        self.client.get(reverse('staff_login', args=['staff-token']))
        nonexistent_pk = self.event_b.pk + 1000
        response = self.client.get(reverse('staff_dashboard', args=[nonexistent_pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer valid')


class ParticipantListUploadViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _upload(self, content_bytes, filename='participants.csv', **extra):
        data = {'csv_file': SimpleUploadedFile(filename, content_bytes)}
        data.update(extra)
        return self.client.post(reverse('participant_list_upload', args=[self.event.pk]), data)

    def test_valid_csv_creates_pending_upload(self):
        csv_bytes = 'name,email\nJane Doe,jane@example.com\nJohn Roe,john@example.com\n'.encode('utf-8')
        response = self._upload(csv_bytes)
        self.assertRedirects(response, reverse('participant_list_preview', args=[self.event.pk]))
        pending = PendingListUpload.objects.get(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT)
        self.assertEqual(pending.rows[0]['name'], 'Jane Doe')
        self.assertEqual(pending.rows[0]['email'], 'jane@example.com')

    def test_missing_email_column_rejected(self):
        response = self._upload('name,phone\nJane Doe,555-1234\n'.encode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'csv_file', response.context['form'].errors['csv_file'])
        self.assertFalse(PendingListUpload.objects.filter(organiser=self.organiser, event=self.event).exists())

    def test_cp1252_csv_decoded_via_fallback(self):
        csv_text = 'name,email\nJoão – Silva,joao@example.com\n'
        csv_bytes = csv_text.encode('cp1252')
        self._upload(csv_bytes)
        pending = PendingListUpload.objects.get(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT)
        self.assertEqual(pending.rows[0]['name'], 'João – Silva')

    def test_oversized_upload_rejected(self):
        row = b'Jane,jane@example.com\n'
        oversized = b'name,email\n' + row * (MAX_UPLOAD_BYTES // len(row) + 1)
        response = self._upload(oversized)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'csv_file', response.context['form'].errors['csv_file'])
        self.assertFalse(PendingListUpload.objects.filter(organiser=self.organiser, event=self.event).exists())

    def test_malformed_email_flagged(self):
        self._upload('name,email\nJane Doe,not-an-email\n'.encode('utf-8'))
        pending = PendingListUpload.objects.get(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT)
        self.assertIn('email', pending.rows[0]['errors'])

    def test_second_upload_replaces_existing_pending_upload(self):
        self._upload('name,email\nJane Doe,jane@example.com\n'.encode('utf-8'))
        self._upload('name,email\nJohn Roe,john@example.com\n'.encode('utf-8'))
        self.assertEqual(
            PendingListUpload.objects.filter(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT).count(), 1,
        )
        pending = PendingListUpload.objects.get(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT)
        self.assertEqual(pending.rows[0]['name'], 'John Roe')

    def test_upload_for_another_organisers_event_returns_404(self):
        other_event = make_event(
            organiser=self.other_organiser, name='Other',
            start_date=date(2027, 2, 1), end_date=date(2027, 2, 2),
            window_start=date(2027, 1, 18), window_end=date(2027, 1, 29),
        )
        response = self.client.post(
            reverse('participant_list_upload', args=[other_event.pk]),
            {'csv_file': SimpleUploadedFile('participants.csv', b'name,email\nJane,jane@example.com\n')},
        )
        self.assertEqual(response.status_code, 404)


def _row(name, email, errors=None):
    return {'name': name, 'email': email, 'errors': errors or {}}


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
        data[f'form-{i}-name'] = row['name']
        data[f'form-{i}-email'] = row['email']
    return data


class ParticipantListPreviewConfirmViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _make_pending(self, rows):
        return PendingListUpload.objects.create(
            organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT, rows=rows,
        )

    def test_page_slices_correct(self):
        rows = [_row(f'Person {i}', f'person{i}@example.com') for i in range(30)]
        self._make_pending(rows)
        response = self.client.get(reverse('participant_list_preview', args=[self.event.pk]), {'page': 2})
        self.assertEqual(response.context['page'], 2)
        self.assertEqual(response.context['total_pages'], 2)
        self.assertEqual(len(response.context['rows']), 5)

    def test_correcting_row_clears_error_and_persists(self):
        pending = self._make_pending([_row('Jane', 'not-an-email', errors={'email': 'Enter a valid email address.'})])
        data = _formset_post_data([_row('Jane', 'jane@example.com')], current_page=1, action='next')
        self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        pending.refresh_from_db()
        self.assertEqual(pending.rows[0]['errors'], {})
        self.assertEqual(pending.rows[0]['email'], 'jane@example.com')

    def test_mismatched_total_forms_rejected(self):
        pending = self._make_pending([_row('Jane', 'jane@example.com'), _row('John', 'john@example.com')])
        data = _formset_post_data([_row('Jane', 'jane@example.com')], current_page=1, action='next')
        data['form-TOTAL_FORMS'] = '1'  # actual page has 2 rows
        response = self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('went wrong', response.context['page_error'])
        pending.refresh_from_db()
        self.assertEqual(len(pending.rows), 2)

    def test_confirm_blocks_on_remaining_error(self):
        pending = self._make_pending([
            _row('Jane', 'jane@example.com'),
            _row('', 'not-an-email', errors={'name': 'Name is required.', 'email': 'Enter a valid email address.'}),
        ])
        data = _formset_post_data(pending.rows, current_page=1, action='confirm')
        response = self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context['page_error'])
        self.assertEqual(Participant.objects.count(), 0)

    def test_confirm_blocks_on_duplicate_within_upload(self):
        pending = self._make_pending([_row('Jane', 'jane@example.com'), _row('Jane Again', 'jane@example.com')])
        data = _formset_post_data(pending.rows, current_page=1, action='confirm')
        response = self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('duplicates', response.context['page_error'])
        self.assertEqual(Participant.objects.count(), 0)

    def test_confirm_blocks_on_duplicate_against_existing_participant(self):
        make_participant(event=self.event, email='jane@example.com', token='existing-participant')
        pending = self._make_pending([_row('Jane', 'jane@example.com')])
        data = _formset_post_data(pending.rows, current_page=1, action='confirm')
        response = self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('already registered', response.context['page_error'])
        self.assertEqual(Participant.objects.count(), 1)

    def test_confirm_blocks_on_duplicate_against_existing_staff_member(self):
        make_staff_member(event=self.event, email='jane@example.com', token='existing-staff')
        pending = self._make_pending([_row('Jane', 'jane@example.com')])
        data = _formset_post_data(pending.rows, current_page=1, action='confirm')
        response = self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('already registered', response.context['page_error'])
        self.assertEqual(Participant.objects.count(), 0)

    def test_confirm_with_valid_data_creates_participants_and_access_links(self):
        pending = self._make_pending([_row('Jane', 'jane@example.com'), _row('John', 'john@example.com')])
        data = _formset_post_data(pending.rows, current_page=1, action='confirm')
        response = self.client.post(reverse('participant_list_preview', args=[self.event.pk]), data)
        self.assertRedirects(response, reverse('event_edit', args=[self.event.pk]))
        self.assertEqual(Participant.objects.filter(event=self.event).count(), 2)
        self.assertFalse(PendingListUpload.objects.filter(pk=pending.pk).exists())
        jane = Participant.objects.get(event=self.event, email='jane@example.com')
        self.assertEqual(jane.access_link.role, AccessLink.ROLE_PARTICIPANT)
        self.assertEqual(jane.access_link.label, 'jane@example.com')
        self.assertEqual(jane.access_link.event_id, self.event.pk)

    def test_preview_for_another_organisers_data_returns_404(self):
        self._make_pending([_row('Jane', 'jane@example.com')])
        self.client.login(username='other@example.com', password='testpass123')
        response = self.client.get(reverse('participant_list_preview', args=[self.event.pk]))
        self.assertEqual(response.status_code, 404)


class StaffListUploadViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _upload(self, content_bytes, filename='staff.csv'):
        return self.client.post(
            reverse('staff_list_upload', args=[self.event.pk]),
            {'csv_file': SimpleUploadedFile(filename, content_bytes)},
        )

    def test_valid_csv_creates_pending_upload(self):
        response = self._upload(b'name,email\nSam Staff,sam@example.com\n')
        self.assertRedirects(response, reverse('staff_list_preview', args=[self.event.pk]))
        pending = PendingListUpload.objects.get(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_STAFF)
        self.assertEqual(pending.rows[0]['name'], 'Sam Staff')
        self.assertEqual(pending.rows[0]['email'], 'sam@example.com')
        self.assertFalse(
            PendingListUpload.objects.filter(event=self.event, role=AccessLink.ROLE_PARTICIPANT).exists(),
        )

    def test_missing_name_column_rejected(self):
        response = self._upload(b'email\nsam@example.com\n')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'csv_file', response.context['form'].errors['csv_file'])
        self.assertFalse(PendingListUpload.objects.filter(organiser=self.organiser, event=self.event).exists())

    def test_malformed_email_flagged(self):
        self._upload(b'name,email\nSam Staff,not-an-email\n')
        pending = PendingListUpload.objects.get(organiser=self.organiser, event=self.event, role=AccessLink.ROLE_STAFF)
        self.assertIn('email', pending.rows[0]['errors'])

    def test_upload_for_another_organisers_event_returns_404(self):
        other_event = make_event(organiser=self.other_organiser, name='Other')
        response = self.client.post(
            reverse('staff_list_upload', args=[other_event.pk]),
            {'csv_file': SimpleUploadedFile('staff.csv', b'name,email\nSam,sam@example.com\n')},
        )
        self.assertEqual(response.status_code, 404)


class StaffListPreviewConfirmViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _make_pending(self, rows):
        return PendingListUpload.objects.create(
            organiser=self.organiser, event=self.event, role=AccessLink.ROLE_STAFF, rows=rows,
        )

    def _confirm(self, pending):
        data = _formset_post_data(pending.rows, current_page=1, action='confirm')
        return self.client.post(reverse('staff_list_preview', args=[self.event.pk]), data)

    def test_confirm_blocks_on_duplicate_within_upload(self):
        pending = self._make_pending([_row('Sam', 'sam@example.com'), _row('Sam Again', 'SAM@example.com')])
        response = self._confirm(pending)
        self.assertEqual(response.status_code, 200)
        self.assertIn('duplicates', response.context['page_error'])
        self.assertEqual(StaffMember.objects.count(), 0)

    def test_confirm_blocks_on_duplicate_against_existing_staff_member(self):
        make_staff_member(event=self.event, email='sam@example.com', token='existing-staff')
        pending = self._make_pending([_row('Sam', 'sam@example.com')])
        response = self._confirm(pending)
        self.assertEqual(response.status_code, 200)
        self.assertIn('already registered', response.context['page_error'])
        self.assertEqual(StaffMember.objects.count(), 1)

    def test_confirm_blocks_on_duplicate_against_existing_participant(self):
        make_participant(event=self.event, email='sam@example.com', token='existing-participant')
        pending = self._make_pending([_row('Sam', 'sam@example.com')])
        response = self._confirm(pending)
        self.assertEqual(response.status_code, 200)
        self.assertIn('already registered', response.context['page_error'])
        self.assertEqual(StaffMember.objects.count(), 0)

    def test_confirm_with_valid_data_creates_staff_members_and_access_links(self):
        pending = self._make_pending([_row('Sam', 'sam@example.com'), _row('Kim', 'kim@example.com')])
        response = self._confirm(pending)
        self.assertRedirects(response, reverse('event_edit', args=[self.event.pk]))
        self.assertEqual(StaffMember.objects.filter(event=self.event).count(), 2)
        self.assertEqual(Participant.objects.count(), 0)
        self.assertFalse(PendingListUpload.objects.filter(pk=pending.pk).exists())
        sam = StaffMember.objects.get(event=self.event, email='sam@example.com')
        self.assertEqual(sam.access_link.role, AccessLink.ROLE_STAFF)
        self.assertEqual(sam.access_link.label, 'sam@example.com')
        self.assertEqual(sam.access_link.event_id, self.event.pk)

    def test_participant_pending_upload_not_visible_in_staff_preview(self):
        PendingListUpload.objects.create(
            organiser=self.organiser, event=self.event, role=AccessLink.ROLE_PARTICIPANT,
            rows=[_row('Jane', 'jane@example.com')],
        )
        response = self.client.get(reverse('staff_list_preview', args=[self.event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_preview_for_another_organisers_data_returns_404(self):
        self._make_pending([_row('Sam', 'sam@example.com')])
        self.client.login(username='other@example.com', password='testpass123')
        response = self.client.get(reverse('staff_list_preview', args=[self.event.pk]))
        self.assertEqual(response.status_code, 404)


class StaffAddOneViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def _add(self, name, email, event=None):
        event = event or self.event
        return self.client.post(reverse('staff_add_one', args=[event.pk]), {'name': name, 'email': email})

    def test_fresh_email_creates_staff_member_and_access_link(self):
        response = self._add('Sam Staff', ' sam@example.com ')
        self.assertRedirects(response, reverse('event_edit', args=[self.event.pk]))
        sam = StaffMember.objects.get(event=self.event)
        self.assertEqual(sam.email, 'sam@example.com')
        self.assertEqual(sam.access_link.role, AccessLink.ROLE_STAFF)
        self.assertEqual(sam.access_link.label, 'sam@example.com')
        self.assertFalse(PendingListUpload.objects.exists())

    def test_email_of_existing_participant_rejected(self):
        make_participant(event=self.event, email='jane@example.com', token='existing-participant')
        response = self._add('Jane', 'JANE@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertIn('already registered', response.context['form'].errors['email'][0])
        self.assertEqual(StaffMember.objects.count(), 0)
        self.assertEqual(AccessLink.objects.filter(role=AccessLink.ROLE_STAFF).count(), 0)

    def test_email_of_existing_staff_member_rejected(self):
        make_staff_member(event=self.event, email='sam@example.com', token='existing-staff')
        response = self._add('Sam Again', 'sam@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertIn('already registered', response.context['form'].errors['email'][0])
        self.assertEqual(StaffMember.objects.count(), 1)

    def test_malformed_email_rejected(self):
        response = self._add('Sam', 'not-an-email')
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertEqual(StaffMember.objects.count(), 0)

    def test_add_for_another_organisers_event_returns_404(self):
        other_event = make_event(organiser=self.other_organiser, name='Other')
        response = self._add('Sam', 'sam@example.com', event=other_event)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(StaffMember.objects.count(), 0)


class EventLinksViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.jane = make_participant(event=self.event, name='Jane Doe', email='jane@example.com', token='jane-token')
        self.sam = make_staff_member(event=self.event, name='Sam Staff', email='sam@example.com', token='sam-token')
        self.client.login(username='organiser@example.com', password='testpass123')

    def test_links_list_shows_both_roles_with_absolute_urls(self):
        response = self.client.get(reverse('event_links', args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        rows = {row['email']: row for row in response.context['rows']}
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows['jane@example.com']['name'], 'Jane Doe')
        self.assertEqual(rows['jane@example.com']['link'], 'http://testserver/participant/jane-token/')
        self.assertEqual(rows['sam@example.com']['name'], 'Sam Staff')
        self.assertEqual(rows['sam@example.com']['link'], 'http://testserver/staff/sam-token/')
        self.assertContains(response, 'http://testserver/participant/jane-token/')

    def test_links_list_excludes_other_events_links(self):
        other_event = make_event(organiser=self.organiser, name='Second Event')
        make_participant(event=other_event, email='elsewhere@example.com', token='elsewhere-token')
        response = self.client.get(reverse('event_links', args=[self.event.pk]))
        emails = [row['email'] for row in response.context['rows']]
        self.assertNotIn('elsewhere@example.com', emails)

    def test_csv_export_has_expected_columns_and_rows(self):
        response = self.client.get(reverse('event_links_export', args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment', response['Content-Disposition'])
        lines = response.content.decode('utf-8-sig').splitlines()
        self.assertEqual(lines[0], 'role,name,email,link')
        self.assertEqual(len(lines), 3)
        self.assertIn('Participant,Jane Doe,jane@example.com,http://testserver/participant/jane-token/', lines)
        self.assertIn('Staff,Sam Staff,sam@example.com,http://testserver/staff/sam-token/', lines)

    def test_csv_export_neutralises_formula_prefixes(self):
        make_participant(event=self.event, name='=HYPERLINK("http://evil")', email='evil@example.com', token='evil-token')
        response = self.client.get(reverse('event_links_export', args=[self.event.pk]))
        content = response.content.decode('utf-8-sig')
        self.assertIn("'=HYPERLINK", content)
        self.assertNotIn(',=HYPERLINK', content)
        self.assertNotIn(',"=HYPERLINK', content)

    def test_links_list_and_export_for_another_organisers_event_return_404(self):
        self.client.login(username='other@example.com', password='testpass123')
        self.assertEqual(self.client.get(reverse('event_links', args=[self.event.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('event_links_export', args=[self.event.pk])).status_code, 404)

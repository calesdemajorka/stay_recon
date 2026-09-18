from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event

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

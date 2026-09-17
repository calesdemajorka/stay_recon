from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event

from .models import AccessLink
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

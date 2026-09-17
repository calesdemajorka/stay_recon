from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from events.models import Event

from .models import AccessLink

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

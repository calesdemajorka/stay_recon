from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import EventForm
from .models import Event
from .views import _save_or_duplicate_error

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

    def test_clean_does_not_crash_with_unset_dates(self):
        # Model.clean() runs unconditionally from ModelForm._post_clean(),
        # even when start_date/end_date failed to parse upstream and are
        # still None on the instance — must not raise TypeError.
        event = Event(name='sss', organiser=self.organiser)
        event.clean()  # should not raise


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

    def test_unparseable_date_format_shows_form_error_not_500(self):
        response = self._post(start_date='16.12.2026', end_date='17.12.2026')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertIn('Enter a valid date.', response.context['form'].errors['start_date'])
        self.assertEqual(Event.objects.count(), 0)

    def test_window_start_after_window_end_rejected(self):
        response = self._post(window_start='2026-09-25', window_end='2026-09-20')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertEqual(Event.objects.count(), 0)

    def test_save_race_converts_integrity_error_to_duplicate_field_error(self):
        # Simulates two concurrent submissions: the form's pre-save
        # duplicate check passes (no conflicting row exists yet), but a
        # conflicting row lands before this form's save() runs.
        form = EventForm(
            data={
                'name': 'Team Offsite',
                'start_date': '2026-10-01',
                'end_date': '2026-10-02',
                'description': '',
            },
            organiser=self.organiser,
        )
        self.assertTrue(form.is_valid())
        make_event(organiser=self.organiser)  # the "concurrent" submission lands first

        self.assertFalse(_save_or_duplicate_error(form))
        self.assertIn('An event with this name and these dates already exists.', form.errors['name'])
        self.assertEqual(Event.objects.count(), 1)


class DashboardAndEditViewTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user(email='organiser@example.com', password='testpass123')
        self.other_organiser = User.objects.create_user(email='other@example.com', password='testpass123')
        self.event = make_event(organiser=self.organiser)
        self.client.login(username='organiser@example.com', password='testpass123')

    def test_dashboard_shows_own_events_ordered_by_start_date(self):
        make_event(
            organiser=self.organiser,
            name='Second Event',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            window_start=date(2026, 8, 18),
            window_end=date(2026, 8, 29),
        )
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(list(response.context['events']), list(self.organiser.events.order_by('start_date')))

    def test_dashboard_hides_other_organisers_events(self):
        make_event(organiser=self.other_organiser, name='Other Org Event')
        response = self.client.get(reverse('dashboard'))
        names = [e.name for e in response.context['events']]
        self.assertNotIn('Other Org Event', names)

    def test_edit_view_404s_for_non_owned_event(self):
        other_event = make_event(organiser=self.other_organiser, name='Other Org Event')
        response = self.client.get(reverse('event_edit', args=[other_event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_edit_with_unchanged_name_and_dates_succeeds(self):
        response = self.client.post(reverse('event_edit', args=[self.event.pk]), {
            'name': self.event.name,
            'start_date': self.event.start_date,
            'end_date': self.event.end_date,
            'description': 'updated description',
            'window_start': self.event.window_start,
            'window_end': self.event.window_end,
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.description, 'updated description')

    def test_edit_colliding_with_different_event_rejected(self):
        other = make_event(
            organiser=self.organiser,
            name='Other Event',
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 2),
            window_start=date(2026, 10, 18),
            window_end=date(2026, 10, 29),
        )
        response = self.client.post(reverse('event_edit', args=[self.event.pk]), {
            'name': other.name,
            'start_date': other.start_date,
            'end_date': other.end_date,
            'description': '',
            'window_start': other.window_start,
            'window_end': other.window_end,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'name', 'An event with this name and these dates already exists.'
        )

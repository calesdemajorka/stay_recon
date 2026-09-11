from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserModelTests(TestCase):
    def test_case_insensitive_email_lookup(self):
        User.objects.create_user(email='A@Example.com', password='testpass123')
        user = User.objects.get(email='a@example.com')
        self.assertEqual(user.email, 'a@example.com')


class LoginLogoutDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='organiser@example.com', password='testpass123')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'organiser@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_logout_clears_session(self):
        self.client.login(username='organiser@example.com', password='testpass123')
        self.client.post(reverse('logout'))
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")


class SignupTests(TestCase):
    def test_valid_signup_creates_user_and_logs_in(self):
        response = self.client.post(reverse('signup'), {
            'email': 'new-organiser@example.com',
            'password1': 'a-strong-passw0rd',
            'password2': 'a-strong-passw0rd',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(User.objects.filter(email='new-organiser@example.com').exists())
        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)

    def test_duplicate_email_rejected_case_insensitive(self):
        User.objects.create_user(email='taken@example.com', password='testpass123')
        response = self.client.post(reverse('signup'), {
            'email': 'Taken@Example.com',
            'password1': 'a-strong-passw0rd',
            'password2': 'a-strong-passw0rd',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', 'An account with this email already exists.')
        self.assertEqual(User.objects.filter(email='taken@example.com').count(), 1)

    def test_malformed_email_rejected(self):
        response = self.client.post(reverse('signup'), {
            'email': 'not-an-email',
            'password1': 'a-strong-passw0rd',
            'password2': 'a-strong-passw0rd',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertIn('email', response.context['form'].errors)

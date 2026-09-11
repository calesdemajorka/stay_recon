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

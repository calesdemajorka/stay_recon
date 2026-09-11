from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_case_insensitive_email_lookup(self):
        User.objects.create_user(email='A@Example.com', password='testpass123')
        user = User.objects.get(email='a@example.com')
        self.assertEqual(user.email, 'a@example.com')

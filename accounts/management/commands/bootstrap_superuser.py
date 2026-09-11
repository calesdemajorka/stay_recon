import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Idempotently create a superuser from env vars.

    Exists because Render's free tier has no SSH/shell/one-off-job runner,
    so `manage.py createsuperuser` can't be run interactively in production.
    Safe to call on every deploy: no-ops when the env vars are unset or the
    account already exists.
    """

    help = 'Create a superuser from DJANGO_SUPERUSER_EMAIL/DJANGO_SUPERUSER_PASSWORD if set and absent.'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not email or not password:
            self.stdout.write('DJANGO_SUPERUSER_EMAIL/PASSWORD not set — skipping.')
            return

        User = get_user_model()
        email = email.lower()
        if User.objects.filter(email=email).exists():
            self.stdout.write(f'Superuser {email} already exists — skipping.')
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(f'Created superuser {email}.')

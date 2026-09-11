import json
import urllib.error
import urllib.request

from django.core.mail.backends.base import BaseEmailBackend


class ResendAPIBackend(BaseEmailBackend):
    """Sends mail via Resend's HTTP API instead of SMTP.

    Render's free tier blocks outbound traffic to SMTP ports (25/465/587)
    as of September 2025, so django.core.mail.backends.smtp can never
    connect from there. HTTPS (443) is not blocked, so Resend's REST API
    is the platform-compatible alternative — stdlib-only, no new dependency.
    """

    api_url = 'https://api.resend.com/emails'

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent = 0
        for message in email_messages:
            payload = {
                'from': message.from_email,
                'to': list(message.to),
                'subject': message.subject,
                'text': message.body,
            }
            request = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                method='POST',
            )
            try:
                with urllib.request.urlopen(request, timeout=10):
                    sent += 1
            except urllib.error.URLError:
                if not self.fail_silently:
                    raise
        return sent

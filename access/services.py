from django.utils import timezone

from .models import AccessLink


def verify_access_link(token, *, role=None):
    """Validate a token and return the AccessLink it authorizes, or None.

    Never raises for an invalid token — unknown, revoked, expired, and
    wrong-role tokens are all indistinguishable None results, so callers
    can't tell a real-but-wrong-role token from one that never existed.
    """
    qs = AccessLink.objects.filter(token=token, is_revoked=False)
    if role is not None:
        qs = qs.filter(role=role)
    access_link = qs.select_related('event').first()
    if access_link is None:
        return None
    if timezone.now().date() > access_link.event.window_end:
        return None
    return access_link

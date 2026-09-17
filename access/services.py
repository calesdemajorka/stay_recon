from django.utils import timezone

from .models import AccessLink

STAFF_SESSION_KEY = 'staff_access_link_id'


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


def establish_staff_session(request, access_link):
    """Record a verified staff AccessLink in the session — no User/account
    is created; the session key is the only persisted state."""
    request.session[STAFF_SESSION_KEY] = access_link.pk


def get_staff_access_link(request, event):
    """Return the session's staff AccessLink if it's still valid for this
    specific event, or None. Re-validates live on every call (not revoked,
    not expired, correct role, correct event) rather than trusting that a
    session grant made earlier is still good — the session-based analogue
    of get_object_or_404(..., organiser=request.user)."""
    access_link_id = request.session.get(STAFF_SESSION_KEY)
    if access_link_id is None:
        return None
    try:
        access_link = AccessLink.objects.select_related('event').get(
            pk=access_link_id, role=AccessLink.ROLE_STAFF, is_revoked=False,
        )
    except AccessLink.DoesNotExist:
        return None
    if access_link.event_id != event.pk:
        return None
    if timezone.now().date() > access_link.event.window_end:
        return None
    return access_link

import secrets

from django.db.models.functions import Lower, Trim
from django.utils import timezone

from .models import AccessLink, Participant, StaffMember

STAFF_SESSION_KEY = 'staff_access_link_id'


def generate_token():
    """A fresh, unguessable access-link token. Collision probability
    against an existing token is astronomically negligible at this
    entropy (256 bits) — no retry-on-collision handling needed."""
    return secrets.token_urlsafe(32)


def email_taken_for_event(email, event):
    """True if `email` already belongs to a Participant or StaffMember for
    this event (either role — dual-role per event is disallowed, so this
    check is deliberately role-agnostic). Normalizes the same way the
    Lower(Trim('email')) DB constraints do."""
    normalized = email.strip().lower()
    participant_taken = Participant.objects.annotate(
        normalized_email=Lower(Trim('email')),
    ).filter(event=event, normalized_email=normalized).exists()
    if participant_taken:
        return True
    return StaffMember.objects.annotate(
        normalized_email=Lower(Trim('email')),
    ).filter(event=event, normalized_email=normalized).exists()


def taken_emails_for_event(event):
    """Every normalized email already used by a Participant or StaffMember
    for this event, as one set — the bulk counterpart of
    email_taken_for_event(), so a full-set check over thousands of staged
    rows costs two queries instead of two per row."""
    taken = set()
    for model in (Participant, StaffMember):
        taken.update(
            model.objects.filter(event=event)
            .annotate(normalized_email=Lower(Trim('email')))
            .values_list('normalized_email', flat=True)
        )
    return taken


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
    is created; the session key is the only persisted state.

    Rotates the session id first: this flow never calls django.contrib
    .auth.login(), so Django wouldn't otherwise rotate it on this
    privilege-elevating event, leaving a pre-existing session id staff-
    privileged once the token is verified.
    """
    request.session.cycle_key()
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

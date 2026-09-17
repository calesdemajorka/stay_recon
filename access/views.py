from django.shortcuts import get_object_or_404, redirect, render

from events.models import Event

from .models import AccessLink
from .services import establish_staff_session, get_staff_access_link, verify_access_link


def participant_access(request, token):
    access_link = verify_access_link(token, role=AccessLink.ROLE_PARTICIPANT)
    if access_link is None:
        return render(request, 'access/link_invalid.html')
    return render(request, 'access/participant_link.html', {'access_link': access_link})


def staff_login(request, token):
    access_link = verify_access_link(token, role=AccessLink.ROLE_STAFF)
    if access_link is None:
        return render(request, 'access/link_invalid.html')
    establish_staff_session(request, access_link)
    return redirect('staff_dashboard', event_pk=access_link.event_id)


def staff_dashboard(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    access_link = get_staff_access_link(request, event)
    if access_link is None:
        return render(request, 'access/link_invalid.html')
    return render(request, 'access/staff_dashboard.html', {'event': event, 'access_link': access_link})

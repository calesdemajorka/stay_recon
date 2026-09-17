from django.shortcuts import render

from .models import AccessLink
from .services import verify_access_link


def participant_access(request, token):
    access_link = verify_access_link(token, role=AccessLink.ROLE_PARTICIPANT)
    if access_link is None:
        return render(request, 'access/link_invalid.html')
    return render(request, 'access/participant_link.html', {'access_link': access_link})

import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from events.models import Event

from .forms import (
    MAX_UPLOAD_BYTES,
    PAGE_SIZE,
    ListRowFormSet,
    ListUploadForm,
    full_set_problems,
    parse_list_csv,
    row_initial,
    validate_row,
)
from .models import AccessLink, Participant, PendingListUpload, StaffMember
from .services import establish_staff_session, generate_token, get_staff_access_link, verify_access_link

DECODE_ENCODINGS = ('utf-8-sig', 'cp1252', 'latin-1')


def _decode_csv_bytes(raw_bytes):
    for encoding in DECODE_ENCODINGS:
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    # latin-1 maps every byte 1:1 and never raises, so this is unreachable —
    # kept only as a defensive fallback.
    return raw_bytes.decode('latin-1', errors='replace')


@login_required
def participant_list_upload(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)

    if request.method == 'POST':
        form = ListUploadForm(request.POST, request.FILES)
        if form.is_valid():
            if form.cleaned_data['csv_file'].size > MAX_UPLOAD_BYTES:
                form.add_error(
                    'csv_file',
                    f'This file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)}MB — check the file and try again.',
                )
            else:
                raw_bytes = form.cleaned_data['csv_file'].read()
                text = _decode_csv_bytes(raw_bytes)
                error, rows = parse_list_csv(text)
                if error:
                    form.add_error('csv_file', error)
                else:
                    PendingListUpload.objects.filter(
                        organiser=request.user, event=event, role=AccessLink.ROLE_PARTICIPANT,
                    ).delete()
                    PendingListUpload.objects.create(
                        organiser=request.user, event=event, role=AccessLink.ROLE_PARTICIPANT, rows=rows,
                    )
                    return redirect('participant_list_preview', event_pk=event.pk)
    else:
        form = ListUploadForm()

    return render(request, 'access/participant_list_upload.html', {'form': form, 'event': event})


def _total_pages(rows):
    return max(1, math.ceil(len(rows) / PAGE_SIZE)) if rows else 1


def _clamp_page(page, total_pages):
    return max(1, min(page, total_pages))


def _render_participant_preview(request, event, page_rows, page, total_pages, page_error=None):
    formset = ListRowFormSet(initial=[row_initial(r) for r in page_rows], prefix='form')
    rows = list(zip(formset, [list(r['errors'].values()) for r in page_rows]))
    return render(request, 'access/participant_list_preview.html', {
        'event': event, 'formset': formset, 'rows': rows,
        'page': page, 'total_pages': total_pages, 'page_error': page_error,
    })


@login_required
def participant_list_preview(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    pending = get_object_or_404(
        PendingListUpload, organiser=request.user, event=event, role=AccessLink.ROLE_PARTICIPANT,
    )
    total_pages = _total_pages(pending.rows)

    if request.method == 'GET':
        try:
            page = _clamp_page(int(request.GET.get('page', 1)), total_pages)
        except ValueError:
            page = 1
        start = (page - 1) * PAGE_SIZE
        page_rows = pending.rows[start:start + PAGE_SIZE]
        return _render_participant_preview(request, event, page_rows, page, total_pages)

    # POST
    try:
        current_page = _clamp_page(int(request.POST.get('current_page', 1)), total_pages)
    except ValueError:
        current_page = 1
    start = (current_page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_rows = pending.rows[start:end]

    # Mirrors rooms' TOTAL_FORMS guard: Django's formset silently drops a
    # mismatched submission rather than raising, so reject and re-render
    # fresh instead of trusting it.
    submitted_total = request.POST.get('form-TOTAL_FORMS')
    if submitted_total is None or not submitted_total.isdigit() or int(submitted_total) != len(page_rows):
        return _render_participant_preview(
            request, event, page_rows, current_page, total_pages,
            page_error='Something went wrong loading this page — please try again.',
        )

    # Save this page's edits (field-level validation only — no cross-page
    # or cross-record duplicate check here; that's confirm-time-only).
    updated_page_rows = []
    for i in range(len(page_rows)):
        name = (request.POST.get(f'form-{i}-name', '') or '').strip()
        email = (request.POST.get(f'form-{i}-email', '') or '').strip()
        updated_page_rows.append(validate_row(name, email))
    pending.rows[start:end] = updated_page_rows
    pending.save(update_fields=['rows'])

    action = request.POST.get('action', 'save')

    if action == 'confirm':
        if not pending.rows:
            return _render_participant_preview(
                request, event, updated_page_rows, current_page, total_pages,
                page_error='No rows found in this CSV.',
            )
        problems = full_set_problems(pending.rows, event)
        if problems:
            return _render_participant_preview(
                request, event, updated_page_rows, current_page, total_pages,
                page_error=' '.join(problems),
            )
        with transaction.atomic():
            for row in pending.rows:
                access_link = AccessLink.objects.create(
                    event=event,
                    role=AccessLink.ROLE_PARTICIPANT,
                    label=row['email'],
                    token=generate_token(),
                )
                participant = Participant(
                    event=event, access_link=access_link, name=row['name'], email=row['email'],
                )
                # Defense-in-depth (plan's Critical Implementation Details):
                # .create()/.save() never trigger clean() on their own, so
                # explicitly re-check the event/role/label invariants this
                # code just constructed by hand.
                participant.full_clean()
                participant.save()
            pending.delete()
        messages.success(request, f'{len(pending.rows)} participant(s) added.')
        return redirect('event_edit', pk=event.pk)

    if action == 'next':
        current_page = _clamp_page(current_page + 1, total_pages)
    elif action == 'previous':
        current_page = _clamp_page(current_page - 1, total_pages)
    return redirect(f"{reverse('participant_list_preview', args=[event.pk])}?page={current_page}")


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
    # A nonexistent event_pk is treated the same as any other invalid
    # session — not a 404 — so this route never distinguishes "no such
    # event" from "not a valid staff session" (see F2, impl-review).
    event = Event.objects.filter(pk=event_pk).first()
    access_link = get_staff_access_link(request, event) if event is not None else None
    if access_link is None:
        return render(request, 'access/link_invalid.html')
    return render(request, 'access/staff_dashboard.html', {'event': event, 'access_link': access_link})

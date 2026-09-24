import csv
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from events.models import Event

from .forms import (
    MAX_UPLOAD_BYTES,
    PAGE_SIZE,
    ListRowFormSet,
    ListUploadForm,
    StaffAddOneForm,
    full_set_problems,
    parse_list_csv,
    row_initial,
    validate_row,
)
from .models import AccessLink, Participant, PendingListUpload, StaffMember
from .services import (
    email_taken_for_event,
    establish_staff_session,
    generate_token,
    get_staff_access_link,
    verify_access_link,
)

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


def _handle_list_upload(request, event, role, template, preview_url_name):
    """Shared upload mechanics for both roles: size cap before reading,
    decode fallback, parse, then replace this organiser's pending
    (unconfirmed) upload for this event+role."""
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
                    PendingListUpload.objects.filter(organiser=request.user, event=event, role=role).delete()
                    PendingListUpload.objects.create(organiser=request.user, event=event, role=role, rows=rows)
                    return redirect(preview_url_name, event_pk=event.pk)
    else:
        form = ListUploadForm()

    return render(request, template, {'form': form, 'event': event})


@login_required
def participant_list_upload(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    return _handle_list_upload(
        request, event, AccessLink.ROLE_PARTICIPANT,
        'access/participant_list_upload.html', 'participant_list_preview',
    )


@login_required
def staff_list_upload(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    return _handle_list_upload(
        request, event, AccessLink.ROLE_STAFF,
        'access/staff_list_upload.html', 'staff_list_preview',
    )


def _total_pages(rows):
    return max(1, math.ceil(len(rows) / PAGE_SIZE)) if rows else 1


def _clamp_page(page, total_pages):
    return max(1, min(page, total_pages))


def _create_member_with_link(event, role, member_model, name, email):
    """Create one AccessLink plus the Participant/StaffMember pointing at it.
    Callers wrap this in transaction.atomic() so a failure never leaves a
    link with no owner. event/role/label are always derived here from the
    row being created, never from an independently-picked AccessLink."""
    access_link = AccessLink.objects.create(event=event, role=role, label=email, token=generate_token())
    member = member_model(event=event, access_link=access_link, name=name, email=email)
    # Defense-in-depth (plan's Critical Implementation Details):
    # .create()/.save() never trigger clean() on their own, so explicitly
    # re-check the event/role/label invariants this code just constructed.
    member.full_clean()
    member.save()
    return member


def _render_list_preview(request, event, template, page_rows, page, total_pages, page_error=None):
    formset = ListRowFormSet(initial=[row_initial(r) for r in page_rows], prefix='form')
    rows = list(zip(formset, [list(r['errors'].values()) for r in page_rows]))
    return render(request, template, {
        'event': event, 'formset': formset, 'rows': rows,
        'page': page, 'total_pages': total_pages, 'page_error': page_error,
    })


def _handle_list_preview(request, event, role, member_model, template, preview_url_name, noun):
    pending = get_object_or_404(PendingListUpload, organiser=request.user, event=event, role=role)
    total_pages = _total_pages(pending.rows)

    if request.method == 'GET':
        try:
            page = _clamp_page(int(request.GET.get('page', 1)), total_pages)
        except ValueError:
            page = 1
        start = (page - 1) * PAGE_SIZE
        page_rows = pending.rows[start:start + PAGE_SIZE]
        return _render_list_preview(request, event, template, page_rows, page, total_pages)

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
        return _render_list_preview(
            request, event, template, page_rows, current_page, total_pages,
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
            return _render_list_preview(
                request, event, template, updated_page_rows, current_page, total_pages,
                page_error='No rows found in this CSV.',
            )
        problems = full_set_problems(pending.rows, event)
        if problems:
            return _render_list_preview(
                request, event, template, updated_page_rows, current_page, total_pages,
                page_error=' '.join(problems),
            )
        with transaction.atomic():
            for row in pending.rows:
                _create_member_with_link(event, role, member_model, row['name'], row['email'])
            pending.delete()
        messages.success(request, f'{len(pending.rows)} {noun}(s) added.')
        return redirect('event_edit', pk=event.pk)

    if action == 'next':
        current_page = _clamp_page(current_page + 1, total_pages)
    elif action == 'previous':
        current_page = _clamp_page(current_page - 1, total_pages)
    return redirect(f"{reverse(preview_url_name, args=[event.pk])}?page={current_page}")


@login_required
def participant_list_preview(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    return _handle_list_preview(
        request, event, AccessLink.ROLE_PARTICIPANT, Participant,
        'access/participant_list_preview.html', 'participant_list_preview', 'participant',
    )


@login_required
def staff_list_preview(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    return _handle_list_preview(
        request, event, AccessLink.ROLE_STAFF, StaffMember,
        'access/staff_list_preview.html', 'staff_list_preview', 'staff member',
    )


@login_required
def staff_add_one(request, event_pk):
    """Direct single-row create-or-reject — no staging model involved."""
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)

    if request.method == 'POST':
        form = StaffAddOneForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            if email_taken_for_event(email, event):
                form.add_error('email', f'{email} is already registered for this event.')
            else:
                try:
                    with transaction.atomic():
                        _create_member_with_link(event, AccessLink.ROLE_STAFF, StaffMember, name, email)
                except IntegrityError:
                    # A concurrent add of the same email won the race past
                    # the check above; the DB constraint caught it.
                    form.add_error('email', f'{email} is already registered for this event.')
                else:
                    messages.success(request, f'Staff member {name} added.')
                    return redirect('event_edit', pk=event.pk)
    else:
        form = StaffAddOneForm()

    return render(request, 'access/staff_add_one.html', {'form': form, 'event': event})


# Leading characters a spreadsheet app treats as the start of a formula
# (lessons.md: CSV export must sanitize formula injection). Tab and CR are
# included too, since some apps strip them and then evaluate what follows.
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _csv_safe(value):
    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


def _event_link_rows(request, event):
    """One dict per AccessLink on this event (both roles): role, the owning
    Participant/StaffMember's name and email, and the absolute URL to share.
    Absolute, not relative: these get pasted into emails outside the app."""
    access_links = (
        AccessLink.objects.filter(event=event)
        .select_related('participant', 'staff_member')
        .order_by('role', 'label')
    )
    rows = []
    for access_link in access_links:
        if access_link.role == AccessLink.ROLE_STAFF:
            owner = getattr(access_link, 'staff_member', None)
            url_name = 'staff_login'
        else:
            owner = getattr(access_link, 'participant', None)
            url_name = 'participant_access'
        rows.append({
            'role': access_link.get_role_display(),
            'name': owner.name if owner else '',
            'email': owner.email if owner else access_link.label,
            'link': request.build_absolute_uri(reverse(url_name, args=[access_link.token])),
        })
    return rows


@login_required
def event_links(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    return render(request, 'access/event_links.html', {
        'event': event, 'rows': _event_link_rows(request, event),
    })


@login_required
def event_links_export(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="event-{event.pk}-links.csv"'
    # BOM so Excel detects UTF-8 and doesn't mangle non-ASCII names.
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['role', 'name', 'email', 'link'])
    for row in _event_link_rows(request, event):
        writer.writerow([_csv_safe(row['role']), _csv_safe(row['name']), _csv_safe(row['email']), row['link']])
    return response


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

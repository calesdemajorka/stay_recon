import csv
import io
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from events.models import Event

from .forms import (
    MAX_HEADER_LENGTH,
    MAX_ROWS,
    MAX_UPLOAD_BYTES,
    PAGE_SIZE,
    ColumnMappingForm,
    CSVUploadForm,
    RoomFormSet,
    compute_mapped_rows,
    full_set_problems,
    row_initial,
    validate_row,
)
from .models import PendingUpload, Room

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
def csv_upload(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    existing_room_count = event.rooms.count()

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            if existing_room_count and not form.cleaned_data['confirm_replace']:
                form.add_error(
                    'confirm_replace',
                    f'This event already has {existing_room_count} confirmed room(s). '
                    'Check the box to confirm you want to replace them.',
                )
            elif form.cleaned_data['csv_file'].size > MAX_UPLOAD_BYTES:
                form.add_error(
                    'csv_file',
                    f'This file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)}MB — check the file and try again.',
                )
            else:
                raw_bytes = form.cleaned_data['csv_file'].read()
                text = _decode_csv_bytes(raw_bytes)

                error = None
                headers, raw_rows = [], []
                try:
                    reader = csv.DictReader(io.StringIO(text, newline=''))
                    headers = reader.fieldnames or []
                    raw_rows = list(reader)
                except csv.Error:
                    error = "This doesn't look like a valid CSV — check the file and try again."

                if error is None:
                    if not headers:
                        error = "This doesn't look like a valid CSV — no header row found."
                    elif any(len(h) > MAX_HEADER_LENGTH for h in headers):
                        error = "This doesn't look like a valid CSV — a column header is implausibly long."
                    elif len(raw_rows) > MAX_ROWS:
                        error = f'This CSV has more than {MAX_ROWS} rows — check the file and try again.'

                if error:
                    form.add_error('csv_file', error)
                else:
                    PendingUpload.objects.filter(organiser=request.user, event=event).delete()
                    PendingUpload.objects.create(
                        organiser=request.user,
                        event=event,
                        headers=headers,
                        raw_rows=raw_rows,
                    )
                    return redirect('rooms_map_columns', event_pk=event.pk)
    else:
        form = CSVUploadForm()

    return render(request, 'rooms/csv_upload.html', {
        'form': form,
        'event': event,
        'existing_room_count': existing_room_count,
    })


@login_required
def csv_map_columns(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    pending = get_object_or_404(PendingUpload, organiser=request.user, event=event)

    if request.method == 'POST':
        form = ColumnMappingForm(request.POST, headers=pending.headers)
        if form.is_valid():
            pending.column_mapping = {
                'room_number': form.cleaned_data['room_number'],
                'room_type': form.cleaned_data['room_type'],
                'capacity': form.cleaned_data['capacity'],
            }
            pending.mapped_rows = compute_mapped_rows(pending.raw_rows, pending.column_mapping)
            pending.save()
            return redirect('rooms_preview', event_pk=event.pk)
    else:
        form = ColumnMappingForm(headers=pending.headers)

    return render(request, 'rooms/csv_map_columns.html', {'form': form, 'event': event})


def _total_pages(mapped_rows):
    return max(1, math.ceil(len(mapped_rows) / PAGE_SIZE)) if mapped_rows else 1


def _clamp_page(page, total_pages):
    return max(1, min(page, total_pages))


def _render_preview(request, event, page_rows, page, total_pages, page_error=None):
    formset = RoomFormSet(initial=[row_initial(r) for r in page_rows], prefix='form')
    rows = list(zip(formset, [list(r['errors'].values()) for r in page_rows]))
    return render(request, 'rooms/csv_preview.html', {
        'event': event, 'formset': formset, 'rows': rows,
        'page': page, 'total_pages': total_pages, 'page_error': page_error,
    })


@login_required
def csv_preview(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk, organiser=request.user)
    pending = get_object_or_404(PendingUpload, organiser=request.user, event=event)
    total_pages = _total_pages(pending.mapped_rows)

    if request.method == 'GET':
        try:
            page = _clamp_page(int(request.GET.get('page', 1)), total_pages)
        except ValueError:
            page = 1
        start = (page - 1) * PAGE_SIZE
        page_rows = pending.mapped_rows[start:start + PAGE_SIZE]
        return _render_preview(request, event, page_rows, page, total_pages)

    # POST
    try:
        current_page = _clamp_page(int(request.POST.get('current_page', 1)), total_pages)
    except ValueError:
        current_page = 1
    start = (current_page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_rows = pending.mapped_rows[start:end]

    # F1 fix (plan review): TOTAL_FORMS must match the expected page-slice
    # length, or Django's formset silently drops the mismatch rather than
    # raising. Reject and re-render fresh rather than trusting it.
    submitted_total = request.POST.get('form-TOTAL_FORMS')
    if submitted_total is None or not submitted_total.isdigit() or int(submitted_total) != len(page_rows):
        return _render_preview(
            request, event, page_rows, current_page, total_pages,
            page_error='Something went wrong loading this page — please try again.',
        )

    # Save this page's edits (field-level validation only — no cross-page
    # duplicate check here; that's confirm-time-only).
    updated_page_rows = []
    for i in range(len(page_rows)):
        room_number = (request.POST.get(f'form-{i}-room_number', '') or '').strip()
        room_type = (request.POST.get(f'form-{i}-room_type', '') or '').strip()
        capacity = (request.POST.get(f'form-{i}-capacity', '') or '').strip()
        updated_page_rows.append(validate_row(room_number, room_type, capacity))
    pending.mapped_rows[start:end] = updated_page_rows
    pending.save(update_fields=['mapped_rows'])

    action = request.POST.get('action', 'save')

    if action == 'confirm':
        if not pending.mapped_rows:
            return _render_preview(
                request, event, updated_page_rows, current_page, total_pages,
                page_error='No rows found in this CSV.',
            )
        problems = full_set_problems(pending.mapped_rows)
        if problems:
            return _render_preview(
                request, event, updated_page_rows, current_page, total_pages,
                page_error=' '.join(problems),
            )
        with transaction.atomic():
            Room.objects.filter(event=event).delete()
            Room.objects.bulk_create([
                Room(
                    event=event,
                    room_number=row['room_number'],
                    room_type=row['room_type'],
                    capacity=int(row['capacity']),
                )
                for row in pending.mapped_rows
            ])
            pending.delete()
        messages.success(request, f'{len(pending.mapped_rows)} room(s) saved.')
        return redirect('event_edit', pk=event.pk)

    if action == 'next':
        current_page = _clamp_page(current_page + 1, total_pages)
    elif action == 'previous':
        current_page = _clamp_page(current_page - 1, total_pages)
    return redirect(f"{reverse('rooms_preview', args=[event.pk])}?page={current_page}")

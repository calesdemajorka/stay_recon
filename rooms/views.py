import csv
import io

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from events.models import Event

from .forms import (
    MAX_HEADER_LENGTH,
    MAX_ROWS,
    ColumnMappingForm,
    CSVUploadForm,
    compute_mapped_rows,
)
from .models import PendingUpload

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


@login_required
def csv_preview(request, event_pk):
    # Placeholder redirect target for Phase 3; fully implemented in Phase 4.
    get_object_or_404(Event, pk=event_pk, organiser=request.user)
    return HttpResponse('Preview, edit, and confirm — coming in Phase 4')

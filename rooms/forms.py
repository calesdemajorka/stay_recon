from django import forms

MAX_ROWS = 5000
MAX_HEADER_LENGTH = 200

TARGET_FIELDS = ('room_number', 'room_type', 'capacity')
TARGET_FIELD_LABELS = {
    'room_number': 'Room number',
    'room_type': 'Room type',
    'capacity': 'Capacity',
}


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()
    confirm_replace = forms.BooleanField(required=False)


class ColumnMappingForm(forms.Form):
    room_number = forms.ChoiceField(label=TARGET_FIELD_LABELS['room_number'])
    room_type = forms.ChoiceField(label=TARGET_FIELD_LABELS['room_type'])
    capacity = forms.ChoiceField(label=TARGET_FIELD_LABELS['capacity'])

    def __init__(self, *args, headers=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(h, h) for h in (headers or [])]
        for field_name in TARGET_FIELDS:
            self.fields[field_name].choices = choices


def validate_row(room_number, room_type, capacity):
    """Field-level validation for one row: missing room number or a
    non-numeric capacity. Never checks for duplicates against other rows —
    that's confirm-time-only (see Phase 4's Critical Implementation
    Detail)."""
    errors = {}
    if not room_number:
        errors['room_number'] = 'Room number is required.'
    if not capacity.isdigit():
        errors['capacity'] = 'Capacity must be a whole number.'
    return {'room_number': room_number, 'room_type': room_type, 'capacity': capacity, 'errors': errors}


def compute_mapped_rows(raw_rows, column_mapping):
    """Apply a column mapping to raw CSV rows, producing target-field dicts
    with a per-row `errors` dict via validate_row()."""
    mapped_rows = []
    for raw_row in raw_rows:
        room_number = (raw_row.get(column_mapping.get('room_number'), '') or '').strip()
        room_type = (raw_row.get(column_mapping.get('room_type'), '') or '').strip()
        capacity_raw = (raw_row.get(column_mapping.get('capacity'), '') or '').strip()
        mapped_rows.append(validate_row(room_number, room_type, capacity_raw))
    return mapped_rows


PAGE_SIZE = 25


class RoomRowForm(forms.Form):
    room_number = forms.CharField(required=False)
    room_type = forms.CharField(required=False)
    capacity = forms.CharField(required=False)


RoomFormSet = forms.formset_factory(RoomRowForm, extra=0)


def row_initial(row):
    return {'room_number': row['room_number'], 'room_type': row['room_type'], 'capacity': row['capacity']}


def full_set_problems(mapped_rows):
    """One pass over the entire mapped_rows list: per-row errors and
    cross-page duplicate room numbers. Returns a list of human-readable
    strings naming the affected page(s)/row(s), or an empty list if clean.
    This is the *only* place duplicate room numbers are checked — per-page
    saves deliberately don't re-run this (see Phase 4's Critical
    Implementation Detail)."""
    problems = []
    seen = {}
    for i, row in enumerate(mapped_rows):
        page = i // PAGE_SIZE + 1
        row_in_page = i % PAGE_SIZE + 1
        if row['errors']:
            problems.append(f'Row {row_in_page} on page {page} has an error.')
        normalized = row['room_number'].strip().lower()
        if normalized:
            if normalized in seen:
                seen_page, seen_row = seen[normalized]
                problems.append(
                    f'Row {row_in_page} on page {page} duplicates the room number '
                    f'of row {seen_row} on page {seen_page}.'
                )
            else:
                seen[normalized] = (page, row_in_page)
    return problems

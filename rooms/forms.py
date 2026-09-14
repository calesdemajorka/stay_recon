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


def compute_mapped_rows(raw_rows, column_mapping):
    """Apply a column mapping to raw CSV rows, producing target-field dicts
    with a per-row `errors` dict for a missing room number or non-numeric
    capacity. Does not check for duplicate room numbers — that check is
    confirm-time-only (see Phase 4's Critical Implementation Detail)."""
    mapped_rows = []
    for raw_row in raw_rows:
        room_number = (raw_row.get(column_mapping.get('room_number'), '') or '').strip()
        room_type = (raw_row.get(column_mapping.get('room_type'), '') or '').strip()
        capacity_raw = (raw_row.get(column_mapping.get('capacity'), '') or '').strip()

        errors = {}
        if not room_number:
            errors['room_number'] = 'Room number is required.'
        if not capacity_raw.isdigit():
            errors['capacity'] = 'Capacity must be a whole number.'

        mapped_rows.append({
            'room_number': room_number,
            'room_type': room_type,
            'capacity': capacity_raw,
            'errors': errors,
        })
    return mapped_rows

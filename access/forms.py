import csv
import io

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .services import email_taken_for_event

MAX_ROWS = 5000
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2MB — generous for a participant/staff list, rejected before reading
MAX_FIELD_VALUE_LENGTH = 254  # matches EmailField's own max_length; also plenty for a name

PAGE_SIZE = 25


class ListUploadForm(forms.Form):
    csv_file = forms.FileField()


def validate_row(name, email):
    """Field-level validation for one row: missing name, missing/malformed
    email. Never checks for duplicates against other rows or existing
    records — that's confirm-time-only, via full_set_problems()."""
    errors = {}
    if not name:
        errors['name'] = 'Name is required.'
    elif len(name) > MAX_FIELD_VALUE_LENGTH:
        errors['name'] = f'Name must be under {MAX_FIELD_VALUE_LENGTH} characters.'
    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if len(email) > MAX_FIELD_VALUE_LENGTH:
                errors['email'] = f'Email must be under {MAX_FIELD_VALUE_LENGTH} characters.'
    return {'name': name, 'email': email, 'errors': errors}


def parse_list_csv(text):
    """Parse a fixed two-column (name, email) CSV — header match is
    case-insensitive, column order doesn't matter. Returns (error, rows):
    error is a friendly string or None; rows is a list of per-row dicts
    from validate_row(), empty on error."""
    try:
        reader = csv.DictReader(io.StringIO(text, newline=''))
        headers = reader.fieldnames or []
        raw_rows = list(reader)
    except csv.Error:
        return "This doesn't look like a valid CSV — check the file and try again.", []

    if not headers:
        return "This doesn't look like a valid CSV — no header row found.", []

    header_map = {h.strip().lower(): h for h in headers}
    if 'name' not in header_map or 'email' not in header_map:
        return "This doesn't look like a valid CSV — expected 'name' and 'email' columns.", []

    if len(raw_rows) > MAX_ROWS:
        return f'This CSV has more than {MAX_ROWS} rows — check the file and try again.', []

    rows = [
        validate_row(
            (raw.get(header_map['name'], '') or '').strip(),
            (raw.get(header_map['email'], '') or '').strip(),
        )
        for raw in raw_rows
    ]
    return None, rows


class ListRowForm(forms.Form):
    name = forms.CharField(required=False)
    email = forms.CharField(required=False)


ListRowFormSet = forms.formset_factory(ListRowForm, extra=0)


def row_initial(row):
    return {'name': row['name'], 'email': row['email']}


def full_set_problems(rows, event):
    """One pass over the entire staged row list: per-row errors, duplicate
    emails within this upload, and duplicate emails against any existing
    Participant/StaffMember for this event (append-only — a match here,
    same role or the other role, always blocks; dual-role per event is
    disallowed). Returns a list of human-readable strings naming the
    affected page(s)/row(s), or an empty list if clean."""
    problems = []
    seen = {}
    for i, row in enumerate(rows):
        page = i // PAGE_SIZE + 1
        row_in_page = i % PAGE_SIZE + 1
        if row['errors']:
            problems.append(f'Row {row_in_page} on page {page} has an error.')
            continue
        normalized = row['email'].strip().lower()
        if normalized in seen:
            seen_page, seen_row = seen[normalized]
            problems.append(
                f'Row {row_in_page} on page {page} duplicates the email '
                f'of row {seen_row} on page {seen_page}.'
            )
        elif email_taken_for_event(row['email'], event):
            problems.append(
                f'Row {row_in_page} on page {page}: {row["email"]} is already registered for this event.'
            )
        else:
            seen[normalized] = (page, row_in_page)
    return problems

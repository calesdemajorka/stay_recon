from django import forms

MAX_ROWS = 5000
MAX_HEADER_LENGTH = 200


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()
    confirm_replace = forms.BooleanField(required=False)

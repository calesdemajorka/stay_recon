from django.db import connection
from django.http import HttpResponse, JsonResponse

INDEX_HTML = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>StayRecon</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 4rem auto; padding: 0 1rem; color: #1a1a1a; }
    h1 { margin-bottom: 0.25rem; }
    p { color: #555; }
  </style>
</head>
<body>
  <h1>StayRecon</h1>
  <p>The app is deployed and running. This is a placeholder landing page &mdash; the real product experience isn't built yet.</p>
</body>
</html>
"""


def index(request):
    return HttpResponse(INDEX_HTML)


def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'status': 'ok'})

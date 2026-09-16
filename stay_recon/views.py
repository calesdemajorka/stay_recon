from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def index(request):
    return render(request, 'landing.html')


def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'status': 'ok'})

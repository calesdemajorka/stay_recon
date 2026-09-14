from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DUPLICATE_ERROR, EventForm
from .models import Event


def _save_or_duplicate_error(form):
    """Save the form, converting a race-condition IntegrityError (two
    concurrent submissions both passing the pre-save duplicate check)
    into the same friendly field error the pre-save check itself raises.
    """
    try:
        with transaction.atomic():
            form.save()
    except IntegrityError:
        form.add_error('name', DUPLICATE_ERROR)
        return False
    return True


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, organiser=request.user)
        if form.is_valid() and _save_or_duplicate_error(form):
            return redirect('dashboard')
    else:
        form = EventForm(organiser=request.user)
    return render(request, 'events/event_form.html', {'form': form})


@login_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, organiser=request.user)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event, organiser=request.user)
        if form.is_valid() and _save_or_duplicate_error(form):
            return redirect('dashboard')
    else:
        form = EventForm(instance=event, organiser=request.user)
    return render(request, 'events/event_form.html', {'form': form})


@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, organiser=request.user)
    if request.method == 'POST':
        event.delete()
        return redirect('dashboard')
    return render(request, 'events/event_confirm_delete.html', {'event': event})

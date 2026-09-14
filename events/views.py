from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EventForm
from .models import Event


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, organiser=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = EventForm(organiser=request.user)
    return render(request, 'events/event_form.html', {'form': form})


@login_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, organiser=request.user)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event, organiser=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = EventForm(instance=event, organiser=request.user)
    return render(request, 'events/event_form.html', {'form': form})

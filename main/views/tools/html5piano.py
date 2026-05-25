
from django.shortcuts import render
import os
from django.conf import settings

def linux(request):
    return render(request, "placeholder.html")

def encrypt(request):
    return render(request, "placeholder.html")

def decrypt(request):
    return render(request, "placeholder.html")

def piano(request):
    path = os.path.join(settings.BASE_DIR, 'static', 'HTML5piano.html')
    with open(path, 'r', encoding='utf-8') as f:
        return HttpResponse(f.read())

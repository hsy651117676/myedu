from django.shortcuts import render

def linux(request):
    return render(request, "linux.html")

def encrypt(request):
    return render(request, "encrypt.html")

def decrypt(request):
    return render(request, "decrypt.html")

def piano(request):
    return render(request, "static/HTML5piano.html")

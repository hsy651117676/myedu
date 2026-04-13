from django.shortcuts import render

def base_info(request):
    return render(request, "base_info.html")

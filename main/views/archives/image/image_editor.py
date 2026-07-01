"""
本地图片自动修图
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def page(request):
    return render(request, "archives/image/image_editor.html")

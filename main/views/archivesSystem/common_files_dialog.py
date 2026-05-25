"""
常用文件 - 弹窗页面
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def add_dialog(request):
    return render(request, "archivesSystem/common_files_add_dialog.html")


@login_required
def edit_dialog(request):
    return render(request, "archivesSystem/common_files_edit_dialog.html")

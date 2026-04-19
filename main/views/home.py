from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ..models import UserProfile  # 导入用户扩展表

@login_required
def home_view(request):
    try:
        real_name = request.user.profile.real_name  # 关联UserProfile取真实姓名
    except UserProfile.DoesNotExist:
        real_name = request.user.username  # 无扩展信息则用用户名
    context = {
        "real_name": real_name  # 模板中用real_name变量
    }
    return render(request, 'index.html', context)

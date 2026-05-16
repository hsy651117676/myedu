from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.cache import cache

@login_required
def home_view(request):
    """主页视图"""
    user = request.user
    
    # 获取真实姓名（优先使用缓存）
    cache_key = f'user_real_name_{user.id}'
    real_name = cache.get(cache_key)
    
    if real_name is None:
        try:
            real_name = user.profile.real_name or user.username
        except:
            real_name = user.username
        cache.set(cache_key, real_name, 3600)  # 缓存1小时
    
    # 获取用户统计信息
    context = {
        "real_name": real_name,
        "username": user.username,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login,
    }
    
    return render(request, 'index.html', context)

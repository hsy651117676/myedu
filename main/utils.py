from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)


def login_required_top(view_func):
    """
    顶部窗口登录检查装饰器
    适用于iframe环境，不是AJAX请求时使用
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # 判断是否为AJAX请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'code': 401, 
                    'msg': '未登录',
                    'redirect': reverse('login')
                }, status=401)
            
            # 非AJAX请求，使用顶部窗口跳转
            next_url = request.build_absolute_uri()
            login_url = f"{reverse('login')}?next={next_url}"
            return HttpResponseRedirect(login_url)
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view


def ajax_login_required(view_func):
    """
    AJAX请求的登录检查装饰器
    返回JSON格式的响应
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401, 
                'msg': '请先登录',
                'redirect': reverse('login')
            }, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped_view

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
import random
import string
import json
import logging
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from functools import wraps

from main.models import UserProfile
from main.utils import ajax_login_required

logger = logging.getLogger(__name__)


# ==================== 常量定义 ====================

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 600  # 10分钟
CODE_EXPIRE_TIME = 300  # 5分钟
SEND_INTERVAL = 60  # 发送间隔60秒
CAPTCHA_LENGTH = 4


# ==================== 装饰器 ====================

def rate_limit(max_attempts, timeout, error_msg):
    """通用频率限制装饰器"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            key = f'rate_limit_{request.path}_{request.META.get("REMOTE_ADDR")}'
            attempts = cache.get(key, 0)
            
            if attempts >= max_attempts:
                return JsonResponse({
                    'code': 429, 
                    'msg': error_msg
                }, status=429)
            
            cache.set(key, attempts + 1, timeout)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def validate_json(required_fields=None):
    """验证JSON请求体和必需字段的装饰器"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'code': 400, 'msg': '请求数据格式错误'}, status=400)
            
            if required_fields:
                missing = [f for f in required_fields if not data.get(f, '').strip()]
                if missing:
                    return JsonResponse({
                        'code': 400, 
                        'msg': f'缺少必需参数: {", ".join(missing)}'
                    }, status=400)
            
            return view_func(request, data, *args, **kwargs)
        return wrapper
    return decorator


# ==================== 验证码 ====================
def generate_captcha(request):
    """生成简洁清晰的验证码"""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    import random
    
    # 创建大尺寸图片
    img = Image.new('RGB', (180, 60), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    
    # 生成4位验证码（排除易混淆字符）
    code = ''.join(random.choices('2346789ABCDEFGHJKLMNPQRTUVWXYZ', k=4))
    request.session['captcha'] = code
    
    # 使用大号字体
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 36)
    except:
        font = ImageFont.load_default()
    
    # 画文字（带简单颜色）
    for i, char in enumerate(code):
        x = 15 + i * 40
        y = 10
        color = (random.randint(0, 80), random.randint(0, 80), random.randint(0, 80))
        draw.text((x, y), char, font=font, fill=color)
    
    # 画几条干扰线
    for _ in range(3):
        x1, y1 = random.randint(0, 60), random.randint(0, 60)
        x2, y2 = random.randint(120, 180), random.randint(0, 60)
        draw.line((x1, y1, x2, y2), fill=(200, 200, 200), width=1)
    
    # 输出
    buf = BytesIO()
    img.save(buf, 'PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


# ==================== 登录 ====================

@ensure_csrf_cookie
def login_view(request):
    """登录视图"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        captcha = request.POST.get('captcha', '').upper()
        
        # 验证验证码
        session_captcha = request.session.get('captcha', '')
        if captcha != session_captcha:
            messages.error(request, '验证码错误')
            return render(request, 'auth/login.html')
        
        # 清除验证码（防止重用）
        request.session.pop('captcha', None)
        
        # 检查登录频率限制
        lock_key = f'login_lock_{username}'
        if cache.get(lock_key):
            messages.error(request, f'账户已锁定，请{LOGIN_LOCKOUT_TIME // 60}分钟后再试')
            return render(request, 'auth/login.html')
        
        # 验证用户
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            # 登录失败处理
            attempts_key = f'login_attempts_{username}'
            attempts = cache.get(attempts_key, 0) + 1
            cache.set(attempts_key, attempts, LOGIN_LOCKOUT_TIME)
            
            if attempts >= MAX_LOGIN_ATTEMPTS:
                cache.set(lock_key, True, LOGIN_LOCKOUT_TIME)
                logger.warning(f"用户 {username} 登录尝试次数过多，已锁定")
                messages.error(request, f'错误次数过多，请{LOGIN_LOCKOUT_TIME // 60}分钟后再试')
            else:
                remaining = MAX_LOGIN_ATTEMPTS - attempts
                messages.error(request, f'用户名或密码错误，还剩 {remaining}/{MAX_LOGIN_ATTEMPTS} 次机会')
            
            return render(request, 'auth/login.html')
        
        # 登录成功
        cache.delete(f'login_attempts_{username}')
        cache.delete(lock_key)
        
        login(request, user)
        logger.info(f"用户 {username} 登录成功")
        
        next_url = request.GET.get('next', '')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('home')
    
    return render(request, 'auth/login.html')


# ==================== 注册 ====================

@require_http_methods(["POST"])
@validate_json(required_fields=['username', 'email', 'password1', 'password2', 'code'])
@rate_limit(10, 3600, '注册请求过于频繁，请1小时后再试')
def send_email_code(request, data):
    """发送注册验证码"""
    email = data['email']
    
    # 检查邮箱是否已注册
    if User.objects.filter(email=email).exists():
        return JsonResponse({'code': 400, 'msg': '该邮箱已被注册'})
    
    # 检查发送频率限制
    send_key = f'email_code_send_{email}'
    if cache.get(send_key):
        return JsonResponse({'code': 400, 'msg': '发送频繁，请60秒后再试'})
    
    # 生成验证码
    code = ''.join(random.choices(string.digits, k=6))
    cache_key = f'register_code_{email}'
    cache.set(cache_key, code, CODE_EXPIRE_TIME)
    cache.set(send_key, True, SEND_INTERVAL)
    
    try:
        send_mail(
            '注册验证码',
            f'您的验证码是: {code}\n有效期 {CODE_EXPIRE_TIME // 60} 分钟，请勿泄露。',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        logger.info(f"验证码已发送至 {email}")
        return JsonResponse({'code': 200, 'msg': '验证码已发送'})
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        cache.delete(cache_key)
        cache.delete(send_key)
        return JsonResponse({'code': 500, 'msg': '邮件发送失败，请稍后重试'})


@require_http_methods(["POST"])
@validate_json(required_fields=['username', 'email', 'password1', 'password2', 'code'])
def register_view(request, data):
    """用户注册"""
    username = data['username']
    email = data['email']
    password1 = data['password1']
    password2 = data['password2']
    code = data['code']
    
    # 验证用户名
    if len(username) < 3:
        return JsonResponse({'code': 400, 'msg': '用户名至少3个字符'})
    
    if not username.isalnum():
        return JsonResponse({'code': 400, 'msg': '用户名只能包含字母和数字'})
    
    # 验证密码
    if len(password1) < 6:
        return JsonResponse({'code': 400, 'msg': '密码长度不能少于6位'})
    
    if password1 != password2:
        return JsonResponse({'code': 400, 'msg': '两次密码不一致'})
    
    # 检查用户名和邮箱唯一性
    if User.objects.filter(username=username).exists():
        return JsonResponse({'code': 400, 'msg': '用户名已存在'})
    
    if User.objects.filter(email=email).exists():
        return JsonResponse({'code': 400, 'msg': '该邮箱已被注册'})
    
    # 验证邮箱验证码
    cache_key = f'register_code_{email}'
    stored_code = cache.get(cache_key)
    
    if not stored_code or stored_code != code:
        return JsonResponse({'code': 400, 'msg': '验证码错误或已过期'})
    
    # 创建用户
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1
        )
        UserProfile.objects.create(user=user)
        
        cache.delete(cache_key)
        logger.info(f"新用户注册成功: {username}")
        
        # 自动登录
        login(request, user)
        return JsonResponse({'code': 200, 'msg': '注册成功', 'redirect': reverse('home')})
        
    except Exception as e:
        logger.error(f"注册失败: {e}")
        return JsonResponse({'code': 500, 'msg': '注册失败，请稍后重试'})


# ==================== 密码重置 ====================

@require_POST
@rate_limit(10, 3600, '请求过于频繁')
def send_reset_code(request):
    """发送密码重置验证码"""
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    
    if not username or not email:
        return JsonResponse({'code': 400, 'msg': '请输入用户名和邮箱'})
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'code': 400, 'msg': '用户名不存在'})
    
    if user.email != email:
        return JsonResponse({'code': 400, 'msg': '用户名与邮箱不匹配'})
    
    # 检查发送频率
    send_key = f'reset_send_{email}'
    if cache.get(send_key):
        return JsonResponse({'code': 400, 'msg': '发送频繁，请60秒后再试'})
    
    # 生成验证码
    code = ''.join(random.choices(string.digits, k=6))
    cache.set(f'reset_code_{email}', code, CODE_EXPIRE_TIME)
    cache.set(send_key, True, SEND_INTERVAL)
    
    try:
        send_mail(
            '密码重置验证码',
            f'您的重置验证码是: {code}\n有效期 {CODE_EXPIRE_TIME // 60} 分钟。',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return JsonResponse({'code': 200, 'msg': '验证码已发送'})
    except Exception as e:
        logger.error(f"重置验证码发送失败: {e}")
        return JsonResponse({'code': 500, 'msg': '邮件发送失败'})


@require_http_methods(["POST"])
@validate_json(required_fields=['username', 'email', 'code', 'password1', 'password2'])
@rate_limit(5, 1800, '重置次数过多，请30分钟后再试')
def forgot_pwd_view(request, data):
    """忘记密码重置"""
    username = data['username']
    email = data['email']
    code = data['code']
    password1 = data['password1']
    password2 = data['password2']
    
    # 验证用户
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'code': 400, 'msg': '用户名不存在'})
    
    if user.email != email:
        return JsonResponse({'code': 400, 'msg': '用户名与邮箱不匹配'})
    
    # 验证密码
    if len(password1) < 6:
        return JsonResponse({'code': 400, 'msg': '密码长度不能少于6位'})
    
    if password1 != password2:
        return JsonResponse({'code': 400, 'msg': '两次密码不一致'})
    
    # 验证重置验证码
    stored_code = cache.get(f'reset_code_{email}')
    if not stored_code or stored_code != code:
        return JsonResponse({'code': 400, 'msg': '验证码错误或已过期'})
    
    # 重置密码
    try:
        user.set_password(password1)
        user.save()
        cache.delete(f'reset_code_{email}')
        logger.info(f"用户 {username} 密码重置成功")
        return JsonResponse({'code': 200, 'msg': '密码重置成功，请登录'})
    except Exception as e:
        logger.error(f"密码重置失败: {e}")
        return JsonResponse({'code': 500, 'msg': '重置失败，请稍后重试'})


# ==================== 用户操作 ====================

@login_required
def logout_view(request):
    """退出登录"""
    username = request.user.username
    logout(request)
    logger.info(f"用户 {username} 退出登录")
    return redirect('login')


@login_required
@require_http_methods(["GET", "POST"])
def change_pwd(request):
    """修改密码"""
    # GET请求返回页面
    if request.method == 'GET':
        return render(request, 'auth/change_pwd.html')
    
    # POST处理
    old_pwd = request.POST.get('old_pwd', '')
    new_pwd1 = request.POST.get('new_pwd1', '')
    new_pwd2 = request.POST.get('new_pwd2', '')
    
    # 频率限制检查
    lock_key = f'change_pwd_lock_{request.user.id}'
    if cache.get(lock_key):
        return JsonResponse({'code': 429, 'msg': '操作过于频繁，请10分钟后再试'})
    
    # 验证旧密码
    if not request.user.check_password(old_pwd):
        attempts = cache.get(f'pwd_attempts_{request.user.id}', 0) + 1
        cache.set(f'pwd_attempts_{request.user.id}', attempts, LOGIN_LOCKOUT_TIME)
        
        if attempts >= 3:
            cache.set(lock_key, True, LOGIN_LOCKOUT_TIME)
            return JsonResponse({'code': 429, 'msg': '错误次数过多，请10分钟后再试'})
        
        return JsonResponse({'code': 400, 'msg': f'旧密码错误，剩余 {3 - attempts} 次机会'})
    
    # 验证新密码
    if len(new_pwd1) < 6:
        return JsonResponse({'code': 400, 'msg': '密码长度不能少于6位'})
    
    if new_pwd1 != new_pwd2:
        return JsonResponse({'code': 400, 'msg': '两次密码不一致'})
    
    if old_pwd == new_pwd1:
        return JsonResponse({'code': 400, 'msg': '新密码不能与旧密码相同'})
    
    # 更新密码
    try:
        request.user.set_password(new_pwd1)
        request.user.save()
        
        # 保持用户登录状态
        update_session_auth_hash(request, request.user)
        
        # 清除尝试记录
        cache.delete(f'pwd_attempts_{request.user.id}')
        
        logger.info(f"用户 {request.user.username} 修改密码成功")
        return JsonResponse({'code': 200, 'msg': '密码修改成功'})
        
    except Exception as e:
        logger.error(f"密码修改失败: {e}")
        return JsonResponse({'code': 500, 'msg': '修改失败，请稍后重试'})


@login_required
@require_http_methods(["GET", "POST"])
def base_info_view(request):
    """用户基本信息管理"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # GET请求返回页面
    if request.method == 'GET':
        return render(request, 'auth/base_info.html', {'profile': profile})
    
    # POST保存信息
    try:
        data = json.loads(request.body)
        
        # 更新信息
        profile.real_name = data.get('real_name', '').strip()
        profile.phone = data.get('phone', '').strip()
        profile.id_card = data.get('id_card', '').strip()
        profile.address = data.get('address', '').strip()
        
        # 验证数据
        profile.full_clean()
        profile.save()
        
        return JsonResponse({'code': 200, 'msg': '保存成功'})
        
    except json.JSONDecodeError:
        return JsonResponse({'code': 400, 'msg': '数据格式错误'})
    except Exception as e:
        logger.error(f"保存用户信息失败: {e}")
        return JsonResponse({'code': 400, 'msg': str(e)})

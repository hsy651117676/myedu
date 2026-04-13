from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
import random
import string
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.core.cache import cache
import json

def generate_captcha(request):
    width, height = 160, 50
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    request.session['captcha'] = code
    for _ in range(10):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(random.randint(0,200), random.randint(0,200), random.randint(0,200)))
    draw.text((25, 8), code, font=font, fill=(255,0,0))
    buf = BytesIO()
    image.save(buf, 'png')
    return HttpResponse(buf.getvalue(), content_type='image/png')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        captcha = request.POST.get('captcha', '').upper()
        session_captcha = request.session.get('captcha', '').upper()
        if captcha != session_captcha:
            messages.error(request, '验证码错误')
            response = render(request, 'auth/login.html')
            return response

        key = f'login_err:{username}'
        err_count = cache.get(key, 0)
        if err_count >= 5:
            messages.error(request, '错误次数过多，请10分钟后再试')
            response = render(request, 'auth/login.html')
            return response

        user = authenticate(request, username=username, password=password)
        if user:
            cache.delete(key)
            login(request, user)
            return redirect('home')

        cache.set(key, err_count + 1, 600)
        messages.error(request, f'用户名或密码错误，已失败 {err_count + 1}/5 次')
        response = render(request, 'auth/login.html')
        return response
    response = render(request, 'auth/login.html')
    return response

def register_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password1 = data.get('password1', '').strip()
        password2 = data.get('password2', '').strip()
        code = data.get('code', '').strip()

        if not username:
            return JsonResponse({'code': 400, 'msg': '请输入用户名'})
        if not email:
            return JsonResponse({'code': 400, 'msg': '请输入邮箱'})
        if len(password1) < 6:
            return JsonResponse({'code': 400, 'msg': '密码长度不能少于6位'})
        if password1 != password2:
            return JsonResponse({'code': 400, 'msg': '两次密码不一致'})
        if User.objects.filter(username=username).exists():
            return JsonResponse({'code': 400, 'msg': '用户名已存在'})
        if User.objects.filter(email=email).exists():
            return JsonResponse({'code': 400, 'msg': '该邮箱已被注册'})
        if not code:
            return JsonResponse({'code': 400, 'msg': '请输入验证码'})

        lock_key = f'register_lock:{email}'
        err_count = cache.get(lock_key, 0)
        if err_count >= 5:
            return JsonResponse({'code': 400, 'msg': '验证码尝试次数过多，请10分钟后再试'})

        cache_code = cache.get(f'email_code:{email}')
        if not cache_code or cache_code != code:
            cache.set(lock_key, err_count + 1, 600)
            return JsonResponse({'code': 400, 'msg': '验证码错误或已过期'})

        User.objects.create_user(username=username, email=email, password=password1)
        cache.delete(f'email_code:{email}')
        cache.delete(lock_key)
        return JsonResponse({'code': 200, 'msg': '注册成功'})

    return render(request, 'auth/register.html')

@require_POST
def send_email_code(request):
    email = request.POST.get('email', '').strip()
    if not email:
        return JsonResponse({'code': 400, 'msg': '请输入邮箱'})
    lock_key = f"email_lock:{email}"
    if cache.get(lock_key):
        return JsonResponse({'code': 400, 'msg': '发送频繁，60秒后再试'})
    code = ''.join(random.choices(string.digits, k=6))
    cache.set(f"email_code:{email}", code, 600)
    cache.set(lock_key, "1", 60)
    send_mail(
        '注册验证码',
        f'您的验证码：{code}（5分钟内有效）',
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False
    )
    return JsonResponse({'code': 200, 'msg': '发送成功'})

def forgot_pwd_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        code = data.get('code', '').strip()
        password1 = data.get('password1', '').strip()
        password2 = data.get('password2', '').strip()

        if not username:
            return JsonResponse({'code':400, 'msg':'请输入用户名'})
        if not email:
            return JsonResponse({'code':400, 'msg':'请输入邮箱'})

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'code':400, 'msg':'用户名不存在'})

        if user.email != email:
            return JsonResponse({'code':400, 'msg':'用户名与邮箱不匹配'})

        if not code:
            return JsonResponse({'code':400, 'msg':'请输入验证码'})
        if not password1:
            return JsonResponse({'code':400, 'msg':'请输入新密码'})
        if len(password1) < 6:
            return JsonResponse({'code':400, 'msg':'密码长度不能少于6位'})
        if password1 != password2:
            return JsonResponse({'code':400, 'msg':'两次密码不一致'})

        lock_key = f'reset_lock:{email}'
        err_count = cache.get(lock_key, 0)
        if err_count >= 5:
            return JsonResponse({'code':400, 'msg':'验证码尝试次数过多，10分钟后再试'})

        cache_code = cache.get(f'reset_code:{email}')
        if not cache_code or cache_code != code:
            cache.set(lock_key, err_count + 1, 600)
            return JsonResponse({'code':400, 'msg':'验证码错误或已过期'})

        user.set_password(password1)
        user.save()
        cache.delete(f'reset_code:{email}')
        cache.delete(lock_key)
        return JsonResponse({'code':200, 'msg':'密码重置成功，请登录'})

    return render(request, 'auth/forgot_pwd.html')

# 发送重置验证码接口
@require_POST
def send_reset_code(request):
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()

    if not username or not email:
        return JsonResponse({'code':400, 'msg':'请输入用户名和邮箱'})

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'code':400, 'msg':'用户名不存在'})

    if user.email != email:
        return JsonResponse({'code':400, 'msg':'用户名与邮箱不匹配'})

    lock_key = f'reset_email_lock:{email}'
    if cache.get(lock_key):
        return JsonResponse({'code':400, 'msg':'发送频繁，60秒后再试'})

    code = ''.join(random.choices(string.digits, k=6))
    cache.set(f'reset_code:{email}', code, 600)
    cache.set(lock_key, '1', 60)

    send_mail(
        '密码重置验证码',
        f'您的重置验证码：{code}（5分钟内有效）',
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False
    )
    return JsonResponse({'code':200, 'msg':'验证码发送成功'})


def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def change_pwd(request):
    user = request.user
    key = f'pwd_err:{user.id}'
    err_count = int(cache.get(key) or 0)

    if err_count >= 3:
        return JsonResponse({'code':429, 'msg':'错误次数过多，10分钟后再试'})

    if request.method == 'POST':
        old_pwd = request.POST.get('old_pwd')
        new_pwd1 = request.POST.get('new_pwd1')
        new_pwd2 = request.POST.get('new_pwd2')

        if not user.check_password(old_pwd):
            cache.set(key, err_count + 1, 600)
            return JsonResponse({'code':400, 'msg':f'旧密码错误，剩余{2-err_count}次机会'})
        if new_pwd1 != new_pwd2:
            return JsonResponse({'code':400, 'msg':'两次密码不一致'})
        if len(new_pwd1) < 4:
            return JsonResponse({'code':400, 'msg':'密码长度不小于4位'})

        user.set_password(new_pwd1)
        user.save()
        login(request, user)
        cache.delete(key)
        return JsonResponse({'code':200, 'msg':'修改成功'})
    return render(request, 'auth/change_pwd.html')

